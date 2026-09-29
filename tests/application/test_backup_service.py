from datetime import date, datetime, timedelta, timezone

import pytest

from application.backup_service import BackupService, ImportResult
from application.credential_service import CredentialInput, CredentialService
from application.errors import VaultLockedError, WrongMasterPasswordError
from application.vault_service import VaultService
from infrastructure.database import connect
from infrastructure.sqlite_vault import SqliteVault

SOURCE_PW = "source-pass"
TARGET_PW = "target-pass"
LATER = datetime(2030, 1, 1, tzinfo=timezone.utc)


class Side:
    def __init__(self, path, master):
        self.conn = connect(str(path))
        store = SqliteVault(self.conn, kdf_n=2**10)
        self.vault = VaultService(store)
        self.vault.setup(master, master)
        self.credentials = CredentialService(self.vault)
        self.backup = BackupService(self.vault, store)

    def titles(self):
        return [c.title.value for c in self.credentials.search().items]


@pytest.fixture
def source(tmp_path):
    side = Side(tmp_path / "source.db", SOURCE_PW)
    yield side
    side.conn.close()


@pytest.fixture
def target(tmp_path):
    side = Side(tmp_path / "target.db", TARGET_PW)
    yield side
    side.conn.close()


def inp(title):
    return CredentialInput(title=title, login_id="me", password="pw", url="", memo="")


def touch(side, credential_id, title, when):
    repo = side.vault.repository()
    c = next(x for x in repo.list_all().items if x.id.value == credential_id)
    c.update(title=title, login_id="me", password="pw", url="", memo="", now=when)
    repo.update(c)


def test_export_then_import_into_empty(source, target):
    source.credentials.add(inp("A"))
    source.credentials.add(inp("B"))
    result = target.backup.import_backup(source.backup.export_backup(), SOURCE_PW)
    assert result == ImportResult(added=2, updated=0, skipped=0)
    assert target.titles() == ["A", "B"]


def test_import_twice_skips_everything(source, target):
    source.credentials.add(inp("A"))
    data = source.backup.export_backup()
    target.backup.import_backup(data, SOURCE_PW)
    assert target.backup.import_backup(data, SOURCE_PW) == ImportResult(0, 0, 1)
    assert target.titles() == ["A"]


def test_newer_backup_overwrites_and_older_is_skipped(source, target):
    a = source.credentials.add(inp("A"))
    b = source.credentials.add(inp("B"))
    target.backup.import_backup(source.backup.export_backup(), SOURCE_PW)
    touch(source, a.id.value, "A-new", LATER)                          # バックアップ側が新しい
    touch(target, b.id.value, "B-target", LATER + timedelta(days=1))   # 取り込み先が新しい
    result = target.backup.import_backup(source.backup.export_backup(), SOURCE_PW)
    assert result == ImportResult(added=0, updated=1, skipped=1)
    assert target.titles() == ["A-new", "B-target"]


def test_wrong_password_writes_nothing(source, target):
    source.credentials.add(inp("A"))
    with pytest.raises(WrongMasterPasswordError):
        target.backup.import_backup(source.backup.export_backup(), "wrong-pass")
    assert target.titles() == []


def test_locked_raises(source, target):
    data = source.backup.export_backup()
    target.vault.lock()
    with pytest.raises(VaultLockedError):
        target.backup.import_backup(data, SOURCE_PW)
    source.vault.lock()
    with pytest.raises(VaultLockedError):
        source.backup.export_backup()


def test_default_file_name():
    assert BackupService.default_file_name(date(2026, 9, 30)) == "passwordapp-backup-20260930.json"
