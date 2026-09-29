from datetime import datetime, timedelta, timezone

import pytest

from domain.credential import Credential, CredentialId, Password, Title, Url
from domain.errors import ValidationError

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make(**overrides) -> Credential:
    args = dict(
        title="GitHub",
        login_id="me@example.com",
        password="s3cret",
        url="https://github.com",
        memo="",
    )
    args.update(overrides)
    return Credential.create(**args, now=T0)


def test_create_sets_fields_and_timestamps():
    c = make()
    assert c.title.value == "GitHub"
    assert c.login_id == "me@example.com"
    assert c.password.value == "s3cret"
    assert c.url == Url("https://github.com")
    assert c.created_at == c.updated_at == T0
    assert len(c.id.value) == 36


def test_new_ids_are_unique():
    assert CredentialId.new() != CredentialId.new()


def test_equality_by_id():
    a = make()
    b = make(title="Other")
    assert a != b
    b.id = a.id
    assert a == b


def test_title_is_trimmed():
    assert Title("  Mail  ").value == "Mail"


@pytest.mark.parametrize("value", ["", "   ", "x" * 101])
def test_invalid_title(value):
    with pytest.raises(ValidationError) as e:
        Title(value)
    assert e.value.field == "title"


def test_title_max_length_ok():
    assert Title("x" * 100).value == "x" * 100


def test_password_required_and_limited():
    with pytest.raises(ValidationError):
        Password("")
    with pytest.raises(ValidationError):
        Password("x" * 257)
    assert Password("x" * 256).value == "x" * 256


def test_password_is_masked_in_str_and_repr():
    p = Password("s3cret")
    assert "s3cret" not in str(p)
    assert "s3cret" not in repr(p)
    assert "s3cret" not in repr(make())


@pytest.mark.parametrize("text", ["https://example.com", "http://example.com/login?x=1"])
def test_valid_url(text):
    assert Url(text).value == text


@pytest.mark.parametrize("text", ["example.com", "ftp://example.com", "https://"])
def test_invalid_url(text):
    with pytest.raises(ValidationError) as e:
        Url(text)
    assert e.value.field == "url"


def test_empty_url_becomes_none():
    assert make(url="  ").url is None


def test_login_id_and_memo_limits():
    with pytest.raises(ValidationError) as e:
        make(login_id="x" * 257)
    assert e.value.field == "login_id"
    with pytest.raises(ValidationError) as e:
        make(memo="x" * 2001)
    assert e.value.field == "memo"


def test_update_changes_fields_and_updated_at_only():
    c = make()
    later = T0 + timedelta(hours=1)
    c.update(title="GitHub 2", login_id="me2", password="new", url="", memo="memo", now=later)
    assert (c.title.value, c.login_id, c.password.value, c.url, c.memo) == (
        "GitHub 2", "me2", "new", None, "memo",
    )
    assert c.created_at == T0
    assert c.updated_at == later


def test_update_with_invalid_value_keeps_old_state():
    c = make()
    with pytest.raises(ValidationError):
        c.update(title="", login_id="", password="p", url="", memo="", now=T0)
    assert c.title.value == "GitHub"


@pytest.mark.parametrize("query", ["git", "  GIT  ", "example", "HUB.COM", ""])
def test_matches(query):
    assert make().matches(query)


def test_matches_memo_and_japanese():
    c = make(title="銀行", memo="暗証番号は別管理")
    assert c.matches("暗証")
    assert c.matches("銀行")
    assert not c.matches("クレジット")
