import pytest

from application.errors import TooManyAttemptsError, VaultLockedError, WrongMasterPasswordError
from application.vault_service import LOCKOUT_SECONDS, MAX_FAILURES, VaultService
from domain.errors import ValidationError
from infrastructure.database import connect
from infrastructure.sqlite_vault import SqliteVault

MASTER = "master-pass"


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def service(tmp_path, clock):
    conn = connect(str(tmp_path / "vault.db"))
    yield VaultService(SqliteVault(conn, kdf_n=2**10), clock=clock)
    conn.close()


def test_setup_requires_8_chars(service):
    with pytest.raises(ValidationError) as e:
        service.setup("short", "short")
    assert e.value.field == "master"
    assert not service.is_initialized()


def test_setup_requires_matching_confirm(service):
    with pytest.raises(ValidationError) as e:
        service.setup(MASTER, MASTER + "x")
    assert e.value.field == "confirm"


def test_setup_unlocks_and_lock_clears(service):
    service.setup(MASTER, MASTER)
    assert service.is_initialized()
    assert service.is_unlocked
    service.repository()
    service.lock()
    assert not service.is_unlocked
    with pytest.raises(VaultLockedError):
        service.repository()


def test_unlock_wrong_then_right(service):
    service.setup(MASTER, MASTER)
    service.lock()
    with pytest.raises(WrongMasterPasswordError):
        service.unlock("wrong-pass")
    assert not service.is_unlocked
    service.unlock(MASTER)
    assert service.is_unlocked


def test_lockout_after_max_failures(service, clock):
    service.setup(MASTER, MASTER)
    service.lock()
    for _ in range(MAX_FAILURES):
        with pytest.raises(WrongMasterPasswordError):
            service.unlock("wrong-pass")
    with pytest.raises(TooManyAttemptsError) as e:
        service.unlock(MASTER)
    assert e.value.retry_after == pytest.approx(LOCKOUT_SECONDS)
    clock.now += LOCKOUT_SECONDS
    service.unlock(MASTER)
    assert service.is_unlocked


def test_success_resets_failure_count(service):
    service.setup(MASTER, MASTER)
    service.lock()
    for _ in range(MAX_FAILURES - 1):
        with pytest.raises(WrongMasterPasswordError):
            service.unlock("wrong-pass")
    service.unlock(MASTER)
    service.lock()
    for _ in range(MAX_FAILURES - 1):
        with pytest.raises(WrongMasterPasswordError):
            service.unlock("wrong-pass")
    service.unlock(MASTER)


def test_change_master_password(service):
    service.setup(MASTER, MASTER)
    with pytest.raises(ValidationError) as e:
        service.change_master_password(MASTER, "short", "short")
    assert e.value.field == "master"
    with pytest.raises(WrongMasterPasswordError):
        service.change_master_password("wrong-pass", "new-password", "new-password")
    service.change_master_password(MASTER, "new-password", "new-password")
    assert service.is_unlocked
    service.lock()
    service.unlock("new-password")


def test_change_master_password_requires_unlocked(service):
    service.setup(MASTER, MASTER)
    service.lock()
    with pytest.raises(VaultLockedError):
        service.change_master_password(MASTER, "new-password", "new-password")


class BlockingStore:
    """open / initialize を外から止められる VaultStore（処理中の割り込みを再現する）。"""

    def __init__(self):
        import threading

        self.started = threading.Event()
        self.release = threading.Event()

    def is_initialized(self):
        return True

    def _slow(self):
        self.started.set()
        assert self.release.wait(5)
        return object()

    def initialize(self, master):
        return self._slow()

    def open(self, master):
        return self._slow()

    def change_master_password(self, current, new):
        return self._slow()


def _run_in_thread(fn, *args):
    import threading

    outcome = {}

    def target():
        try:
            outcome["result"] = fn(*args)
        except Exception as e:  # noqa: BLE001 - テストで結果を受け取るため
            outcome["error"] = e

    thread = threading.Thread(target=target)
    thread.start()
    return thread, outcome


def test_second_operation_while_busy_is_rejected():
    from application.errors import VaultBusyError

    store = BlockingStore()
    service = VaultService(store)
    thread, outcome = _run_in_thread(service.setup, MASTER, MASTER)
    assert store.started.wait(5)
    with pytest.raises(VaultBusyError):
        service.setup(MASTER, MASTER)
    with pytest.raises(VaultBusyError):
        service.repository()
    store.release.set()
    thread.join()
    assert "error" not in outcome
    assert service.is_unlocked


def test_lock_during_unlock_discards_the_result():
    store = BlockingStore()
    service = VaultService(store)
    thread, outcome = _run_in_thread(service.unlock, MASTER)
    assert store.started.wait(5)
    service.lock()
    store.release.set()
    thread.join()
    assert isinstance(outcome.get("error"), VaultLockedError)
    assert not service.is_unlocked


def test_lock_during_change_discards_the_new_repository():
    store = BlockingStore()
    service = VaultService(store)
    service._repository = object()  # 解除済みの状態を作る
    thread, outcome = _run_in_thread(service.change_master_password, MASTER, "new-password", "new-password")
    assert store.started.wait(5)
    service.lock()
    store.release.set()
    thread.join()
    assert isinstance(outcome.get("error"), VaultLockedError)
    assert not service.is_unlocked
