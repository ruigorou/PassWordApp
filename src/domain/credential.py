from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from domain.errors import ValidationError

TITLE_MAX = 100
LOGIN_ID_MAX = 256
PASSWORD_MAX = 256
URL_MAX = 2048
MEMO_MAX = 2000


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class CredentialId:
    value: str

    @staticmethod
    def new() -> CredentialId:
        return CredentialId(str(uuid.uuid4()))


@dataclass(frozen=True)
class Title:
    value: str

    def __post_init__(self):
        value = self.value.strip()
        if not value:
            raise ValidationError("title", "タイトルを入力してください")
        if len(value) > TITLE_MAX:
            raise ValidationError("title", f"タイトルは{TITLE_MAX}文字以内で入力してください")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True)
class Password:
    value: str

    def __post_init__(self):
        if not self.value:
            raise ValidationError("password", "パスワードを入力してください")
        if len(self.value) > PASSWORD_MAX:
            raise ValidationError("password", f"パスワードは{PASSWORD_MAX}文字以内で入力してください")

    def __str__(self) -> str:
        return "********"

    def __repr__(self) -> str:
        return "Password(********)"


@dataclass(frozen=True)
class Url:
    value: str

    def __post_init__(self):
        value = self.value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValidationError("url", "URLは http:// または https:// で始めてください")
        if len(value) > URL_MAX:
            raise ValidationError("url", f"URLは{URL_MAX}文字以内で入力してください")
        object.__setattr__(self, "value", value)

    @staticmethod
    def parse(text: str) -> Url | None:
        return Url(text) if text.strip() else None


def _validated(title: str, login_id: str, password: str, url: str, memo: str):
    title_vo = Title(title)
    login_id = login_id.strip()
    if len(login_id) > LOGIN_ID_MAX:
        raise ValidationError("login_id", f"IDは{LOGIN_ID_MAX}文字以内で入力してください")
    password_vo = Password(password)
    url_vo = Url.parse(url)
    if len(memo) > MEMO_MAX:
        raise ValidationError("memo", f"メモは{MEMO_MAX}文字以内で入力してください")
    return title_vo, login_id, password_vo, url_vo, memo


@dataclass(eq=False)
class Credential:
    id: CredentialId
    title: Title
    login_id: str
    password: Password
    url: Url | None
    memo: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        title: str,
        login_id: str,
        password: str,
        url: str,
        memo: str,
        now: datetime | None = None,
    ) -> Credential:
        now = now or _now()
        return cls(CredentialId.new(), *_validated(title, login_id, password, url, memo), now, now)

    def update(
        self,
        title: str,
        login_id: str,
        password: str,
        url: str,
        memo: str,
        now: datetime | None = None,
    ) -> None:
        self.title, self.login_id, self.password, self.url, self.memo = _validated(
            title, login_id, password, url, memo
        )
        self.updated_at = now or _now()

    def matches(self, query: str) -> bool:
        needle = query.strip().casefold()
        if not needle:
            return True
        haystack = (self.title.value, self.login_id, self.url.value if self.url else "", self.memo)
        return any(needle in text.casefold() for text in haystack)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Credential) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)
