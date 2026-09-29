from datetime import datetime, timedelta, timezone

import pytest

from domain.credential import Credential, CredentialId
from domain.errors import CredentialNotFoundError
from infrastructure.crypto import Cipher
from infrastructure.database import connect
from infrastructure.sqlite_repository import SqliteCredentialRepository

KEY = bytes(range(32))
OTHER_KEY = bytes(range(1, 33))
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "vault.db"


@pytest.fixture
def conn(db_path):
    c = connect(str(db_path))
    yield c
    c.close()


def repo(conn, key=KEY):
    return SqliteCredentialRepository(conn, Cipher(key))


def sample(title="GitHub", **kw):
    args = dict(login_id="me", password="pw", url="", memo="")
    args.update(kw)
    return Credential.create(title=title, **args, now=T0)


def fields(c: Credential):
    return (
        c.id, c.title.value, c.login_id, c.password.value,
        c.url.value if c.url else None, c.memo, c.created_at, c.updated_at,
    )


def test_add_get_list_roundtrip_with_japanese(conn):
    c = sample(title="銀行", login_id="山田", password="パス🔑", url="https://bank.example", memo="暗証番号\n別管理")
    repo(conn).add(c)
    assert fields(repo(conn).get(c.id)) == fields(c)
    result = repo(conn).list_all()
    assert result.unreadable == 0
    assert [fields(x) for x in result.items] == [fields(c)]


def test_get_missing_returns_none(conn):
    assert repo(conn).get(CredentialId.new()) is None


def test_update_and_delete(conn):
    r = repo(conn)
    c = sample()
    r.add(c)
    c.update(title="GitLab", login_id="me", password="new", url="", memo="", now=T0 + timedelta(1))
    r.update(c)
    assert fields(r.get(c.id)) == fields(c)
    r.delete(c.id)
    assert r.get(c.id) is None
    assert r.list_all().items == []


def test_update_missing_raises(conn):
    with pytest.raises(CredentialNotFoundError):
        repo(conn).update(sample())


def test_plaintext_is_not_stored_in_file(conn, db_path):
    c = sample(
        title="UniqueTitleXYZ", login_id="login-ABC", password="pw-QWE",
        url="https://secret-host.example", memo="メモ秘密",
    )
    repo(conn).add(c)
    conn.close()
    data = db_path.read_bytes()
    for secret in ("UniqueTitleXYZ", "login-ABC", "pw-QWE", "secret-host", "メモ秘密"):
        assert secret.encode("utf-8") not in data


def test_wrong_key_counts_as_unreadable(conn):
    c = sample()
    repo(conn).add(c)
    result = repo(conn, OTHER_KEY).list_all()
    assert result.items == []
    assert result.unreadable == 1
    assert repo(conn, OTHER_KEY).get(c.id) is None


def test_swapped_payloads_are_unreadable(conn):
    a, b = sample("A"), sample("B")
    r = repo(conn)
    r.add(a)
    r.add(b)
    pa = conn.execute("SELECT payload FROM credentials WHERE id = ?", (a.id.value,)).fetchone()[0]
    pb = conn.execute("SELECT payload FROM credentials WHERE id = ?", (b.id.value,)).fetchone()[0]
    with conn:
        conn.execute("UPDATE credentials SET payload = ? WHERE id = ?", (pb, a.id.value))
        conn.execute("UPDATE credentials SET payload = ? WHERE id = ?", (pa, b.id.value))
    assert r.list_all().unreadable == 2


def test_upsert_many_inserts_and_overwrites(conn):
    r = repo(conn)
    a = sample("A")
    r.add(a)
    a.update(title="A2", login_id="", password="p", url="", memo="", now=T0 + timedelta(1))
    b = sample("B")
    r.upsert_many([a, b])
    titles = sorted(x.title.value for x in r.list_all().items)
    assert titles == ["A2", "B"]
