import pytest

from application.credential_service import CredentialInput, CredentialService
from application.errors import VaultLockedError
from application.vault_service import VaultService
from domain.errors import CredentialNotFoundError, ValidationError
from infrastructure.database import connect
from infrastructure.sqlite_vault import SqliteVault


@pytest.fixture
def vault(tmp_path):
    conn = connect(str(tmp_path / "vault.db"))
    v = VaultService(SqliteVault(conn, kdf_n=2**10))
    v.setup("master-pass", "master-pass")
    yield v
    conn.close()


@pytest.fixture
def service(vault):
    return CredentialService(vault)


def inp(title="GitHub", login_id="me", password="pw", url="", memo=""):
    return CredentialInput(title=title, login_id=login_id, password=password, url=url, memo=memo)


def titles(result):
    return [c.title.value for c in result.items]


def test_search_is_sorted_case_insensitively(service):
    for t in ("banana", "Apple", "cherry"):
        service.add(inp(t))
    assert titles(service.search()) == ["Apple", "banana", "cherry"]


def test_search_filters(service):
    service.add(inp("GitHub", login_id="dev@example.com"))
    service.add(inp("銀行", memo="暗証番号"))
    assert titles(service.search("EXAMPLE")) == ["GitHub"]
    assert titles(service.search("暗証")) == ["銀行"]
    assert titles(service.search("none")) == []


def test_edit(service):
    c = service.add(inp("GitHub"))
    service.edit(c.id.value, inp("GitLab", password="new"))
    [saved] = service.search().items
    assert (saved.title.value, saved.password.value) == ("GitLab", "new")


def test_edit_missing_raises(service):
    with pytest.raises(CredentialNotFoundError):
        service.edit("00000000-0000-0000-0000-000000000000", inp())


def test_delete(service):
    c = service.add(inp())
    service.delete(c.id.value)
    assert service.search().items == []


def test_validation_error_propagates_and_nothing_saved(service):
    with pytest.raises(ValidationError) as e:
        service.add(inp(title=""))
    assert e.value.field == "title"
    assert service.search().items == []


def test_locked_raises(service, vault):
    vault.lock()
    with pytest.raises(VaultLockedError):
        service.search()


def test_search_reports_unreadable(service, vault):
    service.add(inp("A"))
    conn = vault.repository()._conn
    with conn:
        conn.execute("UPDATE credentials SET payload = x'00'")
    result = service.search()
    assert (result.items, result.unreadable) == ([], 1)
