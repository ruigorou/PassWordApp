import json

import pytest

from application.errors import (
    BackupFormatError,
    CorruptedDataError,
    VaultStateError,
    WrongMasterPasswordError,
)
from domain.credential import Credential
from infrastructure.database import connect
from infrastructure.sqlite_vault import SqliteVault

FAST_N = 2**10
OLD = "old-password"
NEW = "new-password"


@pytest.fixture
def conn(tmp_path):
    c = connect(str(tmp_path / "vault.db"))
    yield c
    c.close()


@pytest.fixture
def other_conn(tmp_path):
    c = connect(str(tmp_path / "other.db"))
    yield c
    c.close()


def vault(conn):
    return SqliteVault(conn, kdf_n=FAST_N)


def sample(title="GitHub", password="pw-secret-123"):
    return Credential.create(title=title, login_id="me", password=password, url="", memo="")


def test_initialize_then_initialized(conn):
    v = vault(conn)
    assert not v.is_initialized()
    v.initialize(OLD)
    assert v.is_initialized()


def test_initialize_twice_raises(conn):
    vault(conn).initialize(OLD)
    with pytest.raises(VaultStateError):
        vault(conn).initialize(OLD)


def test_open_before_initialize_raises(conn):
    with pytest.raises(VaultStateError):
        vault(conn).open(OLD)


def test_open_with_correct_password_reads_data(conn):
    vault(conn).initialize(OLD).add(sample())
    assert [c.title.value for c in vault(conn).open(OLD).list_all().items] == ["GitHub"]


def test_open_with_wrong_password_raises(conn):
    vault(conn).initialize(OLD)
    with pytest.raises(WrongMasterPasswordError):
        vault(conn).open("wrong-password")


def test_japanese_master_password(conn):
    vault(conn).initialize("日本語のマスター鍵🔑").add(sample())
    assert len(vault(conn).open("日本語のマスター鍵🔑").list_all().items) == 1


def test_change_master_password_reencrypts_all(conn):
    repo = vault(conn).initialize(OLD)
    repo.add(sample("A"))
    repo.add(sample("B"))
    new_repo = vault(conn).change_master_password(OLD, NEW)
    assert len(new_repo.list_all().items) == 2
    with pytest.raises(WrongMasterPasswordError):
        vault(conn).open(OLD)
    assert len(vault(conn).open(NEW).list_all().items) == 2


def test_change_master_with_wrong_current_raises(conn):
    vault(conn).initialize(OLD).add(sample())
    with pytest.raises(WrongMasterPasswordError):
        vault(conn).change_master_password("wrong-password", NEW)
    assert len(vault(conn).open(OLD).list_all().items) == 1


def test_change_master_aborts_when_record_is_corrupted(conn):
    repo = vault(conn).initialize(OLD)
    repo.add(sample("A"))
    repo.add(sample("B"))
    with conn:
        conn.execute("UPDATE credentials SET payload = x'00' WHERE rowid = 1")
    with pytest.raises(CorruptedDataError):
        vault(conn).change_master_password(OLD, NEW)
    result = vault(conn).open(OLD).list_all()
    assert (len(result.items), result.unreadable) == (1, 1)


def test_export_contains_no_plaintext(conn):
    vault(conn).initialize(OLD).add(sample("UniqueTitleXYZ", password="pw-secret-123"))
    data = vault(conn).export_backup()
    assert b"UniqueTitleXYZ" not in data
    assert b"pw-secret-123" not in data
    assert json.loads(data)["format"] == "passwordapp-backup"


def test_read_backup_roundtrip_into_other_vault(conn, other_conn):
    original = sample("A")
    vault(conn).initialize(OLD).add(original)
    data = vault(conn).export_backup()
    vault(other_conn).initialize("different-pass")
    restored = vault(other_conn).read_backup(data, OLD)
    assert len(restored) == 1
    c = restored[0]
    assert (c.id, c.title.value, c.password.value, c.created_at, c.updated_at) == (
        original.id, "A", original.password.value, original.created_at, original.updated_at,
    )


def test_read_backup_wrong_password(conn):
    vault(conn).initialize(OLD)
    data = vault(conn).export_backup()
    with pytest.raises(WrongMasterPasswordError):
        vault(conn).read_backup(data, "wrong-password")


def _tampered(conn, mutate):
    vault(conn).initialize(OLD).add(sample())
    doc = json.loads(vault(conn).export_backup())
    mutate(doc)
    return json.dumps(doc).encode()


@pytest.mark.parametrize(
    "make_data",
    [
        lambda conn: b"not json",
        lambda conn: "日本語".encode("shift_jis"),
        lambda conn: b'{"format": "other", "version": 1}',
        lambda conn: b"[]",
        lambda conn: _tampered(conn, lambda d: d["kdf"].__setitem__("n", 2**30)),
        lambda conn: _tampered(conn, lambda d: d.__setitem__("verifier", "***")),
        lambda conn: _tampered(conn, lambda d: d.pop("credentials")),
    ],
)
def test_read_backup_rejects_bad_files(conn, make_data):
    data = make_data(conn)
    with pytest.raises(BackupFormatError):
        vault(conn).read_backup(data, OLD)


def test_read_backup_with_corrupted_record(conn):
    def corrupt(doc):
        doc["credentials"][0]["payload"] = "AAAA"

    data = _tampered(conn, corrupt)
    with pytest.raises(BackupFormatError):
        vault(conn).read_backup(data, OLD)
