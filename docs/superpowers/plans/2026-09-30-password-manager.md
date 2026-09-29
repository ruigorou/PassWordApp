# パスワード管理アプリ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Android で使える、マスターパスワードで暗号化されたパスワード管理アプリ（Flet + SQLite、DDD 4層構成）を作る。

**Architecture:** `domain`（エンティティ・値オブジェクト・生成器・リポジトリ抽象）→ `application`（ユースケースとポート）→ `infrastructure`（scrypt/AES-GCM、SQLite 実装）→ `presentation`（Flet 画面）。全項目を 1 レコード 1 暗号文として保存し、鍵はメモリ上のみに置く。組み立ては `src/main.py`。

**Tech Stack:** Python 3.14（venv はプロジェクト直下）、Flet 1.0.2、`cryptography`（AESGCM / Scrypt）、標準 `sqlite3` / `secrets`、pytest + pytest-asyncio。

**Spec:** `docs/superpowers/specs/2026-09-30-password-manager-design.md`

## Global Constraints

- コマンドはすべてプロジェクトルート `C:\Users\kai59\デスクトップ\PassWordApp` で、venv の `Scripts/python` を使って実行する（例: `Scripts/python -m pytest tests -v`）。
- git リポジトリは未初期化のため、各タスクのコミット手順はない。
- 依存: `flet>=1.0.2`, `cryptography>=43`（Flet の Android 用パッケージ置き場に cp312 / cp314 の Android wheel があることを確認済み）。
- マスターパスワード 8文字以上。scrypt 本番値 n=2^15, r=8, p=1, 鍵 32バイト, ソルト 16バイト。AES-256-GCM, nonce 12バイト, AAD = レコード ID。
- タイトル 1〜100文字（前後空白除去）、ID 256文字まで、パスワード 1〜256文字、URL は空 or http(s)://ホスト、メモ 2000文字まで。
- パスワード生成: 長さ 8〜64（初期値 16）、文字種は最低1種・選んだ種類を各1文字以上含む。
- ロック解除 5回連続失敗で 30秒間入力を受け付けない。無操作 5分で自動ロック。バックグラウンド（HIDE / PAUSE）で即ロック。
- クリップボードは 30秒後、中身が同じ場合のみ消去。
- DB ファイル: `FLET_APP_STORAGE_DATA/vault.db`（未設定時は `~/.passwordapp/vault.db`）。
- バックアップ形式: `{"format": "passwordapp-backup", "version": 1, ...}`、ファイル名 `passwordapp-backup-YYYYMMDD.json`。
- テストでは scrypt を n=2^10 にして高速化する（本番定数は変えない）。
- 画面の文言は日本語。ドメイン層は Flet / sqlite3 / cryptography を import しない。
- Task 11 以降、ユニットテストは `Scripts/python -m pytest tests --ignore=tests/ui -v` で実行する（UI テストは `flet test` 専用）。

## Review Focus

1. Android でファイル選択画面を開くとアプリがバックグラウンド扱い（HIDE/PAUSE）になる → エクスポート／インポート中に自動ロックされてはいけない（Task 8 `test_suspended_blocks_background_lock_and_idle`）。
2. 同じバックアップを2回読み込む → 重複登録されず、すべてスキップになる（Task 7 `test_import_twice_skips_everything`）。
3. 読めない（破損した）レコードがある状態でマスターパスワードを変更 → 変更を中断し、旧パスワードで引き続き開ける（Task 5 `test_change_master_aborts_when_record_is_corrupted`）。
4. 日本語などの非 ASCII 文字（タイトル・メモ・マスターパスワード）→ 保存・復号・検索で文字化けしない（Task 1 `test_matches_memo_and_japanese`、Task 4 `test_add_get_list_roundtrip_with_japanese`、Task 5 `test_japanese_master_password`）。
5. 改ざんされたバックアップ（巨大な scrypt パラメータ・不正 JSON）→ 固まらず「形式が正しくありません」で終わる（Task 5 `test_read_backup_rejects_bad_files`）。

## ファイル構成

| ファイル | 責務 |
|---|---|
| `src/main.py` | DB パス決定と依存の組み立て、`ft.run` |
| `src/domain/errors.py` | `DomainError` / `ValidationError` / `CredentialNotFoundError` |
| `src/domain/credential.py` | `Credential` エンティティ、`CredentialId` / `Title` / `Password` / `Url` |
| `src/domain/password_generator.py` | `GeneratorOptions` / `PasswordGenerator` |
| `src/domain/repository.py` | `CredentialRepository`（抽象）/ `CredentialList` |
| `src/application/errors.py` | 画面表示用メッセージ付きの例外群 |
| `src/application/ports.py` | `VaultStore`（インフラが実装するポート） |
| `src/application/vault_service.py` | 初期設定・解除・ロック・失敗回数制限・マスターPW変更 |
| `src/application/credential_service.py` | `CredentialInput` / 検索・追加・編集・削除 |
| `src/application/backup_service.py` | `ImportResult` / エクスポート・インポートのマージ |
| `src/infrastructure/crypto.py` | `KdfParams` / `derive_key` / `Cipher` / verifier |
| `src/infrastructure/database.py` | `connect`・スキーマ |
| `src/infrastructure/credential_codec.py` | Credential ⇔ 暗号文 |
| `src/infrastructure/sqlite_repository.py` | `SqliteCredentialRepository` |
| `src/infrastructure/sqlite_vault.py` | `SqliteVault`（`VaultStore` 実装、バックアップ入出力） |
| `src/presentation/session_guard.py` | `AutoLock` / `ClipboardCleaner`（Flet 非依存でテスト可能） |
| `src/presentation/app.py` | `PasswordApp`（画面切替・ロック・通知・コピー）/ `Screen` |
| `src/presentation/views/lock_views.py` | 初期設定画面・ロック解除画面 |
| `src/presentation/views/list_view.py` | 一覧・検索 |
| `src/presentation/views/edit_view.py` | 登録・編集・削除 |
| `src/presentation/views/generator_view.py` | 生成パネル・生成画面・生成ダイアログ |
| `src/presentation/views/settings_view.py` | マスターPW変更・バックアップ |

---

### Task 1: 環境準備とドメインモデル（Credential・値オブジェクト）

**Files:**
- Modify: `pyproject.toml`（dependencies / dev 依存）
- Delete: `tests/test_main.py`（カウンターのサンプルテスト）
- Create: `src/domain/__init__.py`, `src/application/__init__.py`, `src/infrastructure/__init__.py`, `src/presentation/__init__.py`, `src/presentation/views/__init__.py`（すべて空）
- Create: `src/domain/errors.py`, `src/domain/credential.py`
- Test: `tests/domain/test_credential.py`

**Interfaces:**
- Produces:
  - `DomainError(message: str)`（`.message`）、`ValidationError(field: str, message: str)`（`.field`, `.message`）、`CredentialNotFoundError()`
  - `CredentialId(value: str)`, `CredentialId.new() -> CredentialId`
  - `Title(value: str)`, `Password(value: str)`, `Url(value: str)`, `Url.parse(text: str) -> Url | None`
  - `Credential.create(title, login_id, password, url, memo, now: datetime | None = None) -> Credential`
  - `Credential.update(title, login_id, password, url, memo, now: datetime | None = None) -> None`
  - `Credential.matches(query: str) -> bool`
  - 属性: `id, title, login_id, password, url, memo, created_at, updated_at`

- [ ] **Step 1: 依存を追加してインストール**

`pyproject.toml` の該当箇所を次のように変更:

```toml
dependencies = [
    "flet>=1.0.2",
    "cryptography>=43",
]

[dependency-groups]
dev = [
    "flet-cli>=1.0.2",
    "flet-desktop>=1.0.2",
    "flet-web>=1.0.2",
    # Integration testing with `flet test` / pytest. The `test` extra brings in
    # pytest, pytest-asyncio and the screenshot-comparison dependencies.
    "flet[test]>=1.0.2",
    "pytest>=8",
    "pytest-asyncio>=0.23",
]
```

Run: `Scripts/python -m pip install "cryptography>=43" "pytest>=8" "pytest-asyncio>=0.23"`
Expected: `Successfully installed ...`（すでにある場合は `Requirement already satisfied`）

- [ ] **Step 2: サンプルテストを削除し、パッケージを作る**

`tests/test_main.py` を削除。`src/domain/__init__.py` など上記 5 つの空ファイルを作成。

- [ ] **Step 3: 失敗するテストを書く** — `tests/domain/test_credential.py`

```python
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
```

- [ ] **Step 4: テストが失敗することを確認**

Run: `Scripts/python -m pytest tests/domain/test_credential.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'domain.credential'`）

- [ ] **Step 5: 実装** — `src/domain/errors.py`

```python
class DomainError(Exception):
    """業務ルール違反。message は画面にそのまま表示できる文言。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ValidationError(DomainError):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


class CredentialNotFoundError(DomainError):
    def __init__(self):
        super().__init__("データが見つかりません")
```

`src/domain/credential.py`

```python
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
```

- [ ] **Step 6: テストが通ることを確認**

Run: `Scripts/python -m pytest tests/domain/test_credential.py -v`
Expected: すべて PASS

---

### Task 2: パスワード生成（ドメインサービス）

**Files:**
- Create: `src/domain/password_generator.py`
- Test: `tests/domain/test_password_generator.py`

**Interfaces:**
- Consumes: `ValidationError`（Task 1）
- Produces: `MIN_LENGTH=8`, `MAX_LENGTH=64`, `DEFAULT_LENGTH=16`, `SYMBOLS: str`, `GeneratorOptions(length=16, lowercase=True, uppercase=True, digits=True, symbols=True)`, `PasswordGenerator().generate(options: GeneratorOptions = GeneratorOptions()) -> str`。エラーは `ValidationError("length", ...)` / `ValidationError("charset", ...)`。

- [ ] **Step 1: 失敗するテストを書く** — `tests/domain/test_password_generator.py`

```python
import string

import pytest

from domain.errors import ValidationError
from domain.password_generator import SYMBOLS, GeneratorOptions, PasswordGenerator

KINDS = (string.ascii_lowercase, string.ascii_uppercase, string.digits, SYMBOLS)


def test_default_is_16_chars_with_every_kind():
    for _ in range(50):
        pw = PasswordGenerator().generate()
        assert len(pw) == 16
        for kind in KINDS:
            assert any(ch in kind for ch in pw)


@pytest.mark.parametrize("length", [8, 64])
def test_boundary_lengths(length):
    assert len(PasswordGenerator().generate(GeneratorOptions(length=length))) == length


@pytest.mark.parametrize("length", [7, 65])
def test_out_of_range_length(length):
    with pytest.raises(ValidationError) as e:
        PasswordGenerator().generate(GeneratorOptions(length=length))
    assert e.value.field == "length"


def test_only_digits():
    options = GeneratorOptions(lowercase=False, uppercase=False, symbols=False)
    assert PasswordGenerator().generate(options).isdigit()


def test_no_kind_selected():
    options = GeneratorOptions(lowercase=False, uppercase=False, digits=False, symbols=False)
    with pytest.raises(ValidationError) as e:
        PasswordGenerator().generate(options)
    assert e.value.field == "charset"


def test_min_length_still_contains_every_kind():
    for _ in range(200):
        pw = PasswordGenerator().generate(GeneratorOptions(length=8))
        for kind in KINDS:
            assert any(ch in kind for ch in pw)


def test_outputs_differ():
    generator = PasswordGenerator()
    assert len({generator.generate() for _ in range(20)}) == 20
```

- [ ] **Step 2: 失敗を確認**

Run: `Scripts/python -m pytest tests/domain/test_password_generator.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 実装** — `src/domain/password_generator.py`

```python
import secrets
import string
from dataclasses import dataclass

from domain.errors import ValidationError

MIN_LENGTH = 8
MAX_LENGTH = 64
DEFAULT_LENGTH = 16
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?/"


@dataclass(frozen=True)
class GeneratorOptions:
    length: int = DEFAULT_LENGTH
    lowercase: bool = True
    uppercase: bool = True
    digits: bool = True
    symbols: bool = True


class PasswordGenerator:
    def __init__(self):
        self._rng = secrets.SystemRandom()

    def generate(self, options: GeneratorOptions = GeneratorOptions()) -> str:
        if not MIN_LENGTH <= options.length <= MAX_LENGTH:
            raise ValidationError("length", f"長さは{MIN_LENGTH}〜{MAX_LENGTH}で指定してください")
        pools = [
            pool
            for enabled, pool in (
                (options.lowercase, string.ascii_lowercase),
                (options.uppercase, string.ascii_uppercase),
                (options.digits, string.digits),
                (options.symbols, SYMBOLS),
            )
            if enabled
        ]
        if not pools:
            raise ValidationError("charset", "文字の種類を1つ以上選んでください")
        # 選んだ種類を1文字ずつ確保してから残りを埋め、最後に混ぜる
        chars = [self._rng.choice(pool) for pool in pools]
        alphabet = "".join(pools)
        chars += [self._rng.choice(alphabet) for _ in range(options.length - len(chars))]
        self._rng.shuffle(chars)
        return "".join(chars)
```

- [ ] **Step 4: 通ることを確認**

Run: `Scripts/python -m pytest tests/domain -v`
Expected: すべて PASS

---

### Task 3: 暗号（鍵導出・AES-GCM・verifier）

**Files:**
- Create: `src/infrastructure/crypto.py`
- Test: `tests/infrastructure/test_crypto.py`

**Interfaces:**
- Produces:
  - 定数 `DEFAULT_KDF_N = 2**15`, `MAX_KDF_N = 2**20`, `SALT_SIZE = 16`, `NONCE_SIZE = 12`
  - `KdfParams(salt: bytes, n: int, r: int, p: int)`（不正値は `ValueError`）、`KdfParams.generate(n=DEFAULT_KDF_N, r=8, p=1) -> KdfParams`
  - `derive_key(password: str, params: KdfParams) -> bytes`（32バイト）
  - `Cipher(key: bytes)`: `.encrypt(plaintext: bytes, aad: bytes) -> bytes`, `.decrypt(blob: bytes, aad: bytes) -> bytes`
  - `DecryptionError(Exception)`
  - `make_verifier(cipher: Cipher) -> bytes`, `check_verifier(cipher: Cipher, blob: bytes) -> bool`

- [ ] **Step 1: 失敗するテストを書く** — `tests/infrastructure/test_crypto.py`

```python
import os

import pytest

from infrastructure.crypto import (
    Cipher,
    DecryptionError,
    KdfParams,
    check_verifier,
    derive_key,
    make_verifier,
)

FAST_N = 2**10


def test_derive_key_is_deterministic_per_salt():
    params = KdfParams.generate(n=FAST_N)
    key = derive_key("パスワード", params)
    assert len(key) == 32
    assert derive_key("パスワード", params) == key
    assert derive_key("パスワード", KdfParams.generate(n=FAST_N)) != key
    assert derive_key("other", params) != key


def test_roundtrip_with_japanese():
    cipher = Cipher(os.urandom(32))
    blob = cipher.encrypt("日本語のメモ".encode(), b"id-1")
    assert cipher.decrypt(blob, b"id-1").decode() == "日本語のメモ"


def test_same_plaintext_encrypts_differently():
    cipher = Cipher(os.urandom(32))
    assert cipher.encrypt(b"x", b"a") != cipher.encrypt(b"x", b"a")


def test_wrong_key_fails():
    blob = Cipher(os.urandom(32)).encrypt(b"x", b"a")
    with pytest.raises(DecryptionError):
        Cipher(os.urandom(32)).decrypt(blob, b"a")


def test_wrong_aad_fails():
    cipher = Cipher(os.urandom(32))
    blob = cipher.encrypt(b"x", b"id-1")
    with pytest.raises(DecryptionError):
        cipher.decrypt(blob, b"id-2")


def test_tampered_blob_fails():
    cipher = Cipher(os.urandom(32))
    blob = bytearray(cipher.encrypt(b"x", b"a"))
    blob[-1] ^= 0x01
    with pytest.raises(DecryptionError):
        cipher.decrypt(bytes(blob), b"a")


def test_short_blob_fails():
    with pytest.raises(DecryptionError):
        Cipher(os.urandom(32)).decrypt(b"\x00" * 5, b"a")


def test_verifier():
    cipher = Cipher(os.urandom(32))
    verifier = make_verifier(cipher)
    assert check_verifier(cipher, verifier)
    assert not check_verifier(Cipher(os.urandom(32)), verifier)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(n=3),
        dict(n=2**21),
        dict(n="1024"),
        dict(r=0),
        dict(p=5),
        dict(salt=b"short"),
    ],
)
def test_invalid_kdf_params(kwargs):
    args = dict(salt=os.urandom(16), n=FAST_N, r=8, p=1)
    args.update(kwargs)
    with pytest.raises(ValueError):
        KdfParams(**args)
```

- [ ] **Step 2: 失敗を確認**

Run: `Scripts/python -m pytest tests/infrastructure/test_crypto.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 実装** — `src/infrastructure/crypto.py`

```python
from __future__ import annotations

import os
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

DEFAULT_KDF_N = 2**15
DEFAULT_KDF_R = 8
DEFAULT_KDF_P = 1
MAX_KDF_N = 2**20  # 改ざんされたバックアップで端末が固まらないための上限
SALT_SIZE = 16
NONCE_SIZE = 12
TAG_SIZE = 16
KEY_SIZE = 32

VERIFIER_PLAINTEXT = b"passwordapp-vault-v1"
VERIFIER_AAD = b"verifier"


class DecryptionError(Exception):
    pass


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class KdfParams:
    salt: bytes = field(repr=False)
    n: int = DEFAULT_KDF_N
    r: int = DEFAULT_KDF_R
    p: int = DEFAULT_KDF_P

    def __post_init__(self):
        valid = (
            isinstance(self.salt, bytes)
            and len(self.salt) >= SALT_SIZE
            and _is_int(self.n)
            and 2 <= self.n <= MAX_KDF_N
            and self.n & (self.n - 1) == 0
            and _is_int(self.r)
            and 1 <= self.r <= 16
            and _is_int(self.p)
            and 1 <= self.p <= 4
        )
        if not valid:
            raise ValueError("KDF パラメータが不正です")

    @classmethod
    def generate(
        cls, n: int = DEFAULT_KDF_N, r: int = DEFAULT_KDF_R, p: int = DEFAULT_KDF_P
    ) -> KdfParams:
        return cls(os.urandom(SALT_SIZE), n, r, p)


def derive_key(password: str, params: KdfParams) -> bytes:
    kdf = Scrypt(salt=params.salt, length=KEY_SIZE, n=params.n, r=params.r, p=params.p)
    return kdf.derive(password.encode("utf-8"))


class Cipher:
    def __init__(self, key: bytes):
        self._aead = AESGCM(key)

    def encrypt(self, plaintext: bytes, aad: bytes) -> bytes:
        nonce = os.urandom(NONCE_SIZE)
        return nonce + self._aead.encrypt(nonce, plaintext, aad)

    def decrypt(self, blob: bytes, aad: bytes) -> bytes:
        if len(blob) < NONCE_SIZE + TAG_SIZE:
            raise DecryptionError("暗号文が短すぎます")
        try:
            return self._aead.decrypt(blob[:NONCE_SIZE], blob[NONCE_SIZE:], aad)
        except InvalidTag as e:
            raise DecryptionError("復号に失敗しました") from e


def make_verifier(cipher: Cipher) -> bytes:
    return cipher.encrypt(VERIFIER_PLAINTEXT, VERIFIER_AAD)


def check_verifier(cipher: Cipher, blob: bytes) -> bool:
    try:
        return cipher.decrypt(blob, VERIFIER_AAD) == VERIFIER_PLAINTEXT
    except DecryptionError:
        return False
```

- [ ] **Step 4: 通ることを確認**

Run: `Scripts/python -m pytest tests/infrastructure/test_crypto.py -v`
Expected: すべて PASS

---

### Task 4: リポジトリ（抽象・SQLite 実装・暗号化コーデック）

**Files:**
- Create: `src/domain/repository.py`, `src/infrastructure/database.py`, `src/infrastructure/credential_codec.py`, `src/infrastructure/sqlite_repository.py`
- Test: `tests/infrastructure/test_sqlite_repository.py`

**Interfaces:**
- Consumes: `Credential` 系（Task 1）、`Cipher` / `DecryptionError`（Task 3）、`CredentialNotFoundError`（Task 1）
- Produces:
  - `CredentialList(items: list[Credential], unreadable: int)`
  - `CredentialRepository`（抽象）: `list_all() -> CredentialList`, `get(credential_id: CredentialId) -> Credential | None`（復号できない場合も `None`）, `add(c)`, `update(c)`（無ければ `CredentialNotFoundError`）, `delete(credential_id)`, `upsert_many(credentials: list[Credential])`（1トランザクション）
  - `SCHEMA_VERSION = 1`, `connect(path: str) -> sqlite3.Connection`（`row_factory=sqlite3.Row`、`check_same_thread=False`、スキーマ作成済み）
  - `encrypt_credential(cipher, c) -> bytes`, `decrypt_credential(cipher, credential_id: str, payload: bytes, created_at: str, updated_at: str) -> Credential`, `DECODE_ERRORS`（復号・解析失敗として扱う例外のタプル）
  - `SqliteCredentialRepository(conn: sqlite3.Connection, cipher: Cipher)`

- [ ] **Step 1: 失敗するテストを書く** — `tests/infrastructure/test_sqlite_repository.py`

```python
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
```

- [ ] **Step 2: 失敗を確認**

Run: `Scripts/python -m pytest tests/infrastructure/test_sqlite_repository.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 実装**

`src/domain/repository.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

from domain.credential import Credential, CredentialId


@dataclass(frozen=True)
class CredentialList:
    items: list[Credential]
    unreadable: int  # 復号できなかった件数


class CredentialRepository(ABC):
    @abstractmethod
    def list_all(self) -> CredentialList: ...

    @abstractmethod
    def get(self, credential_id: CredentialId) -> Credential | None:
        """見つからない、または復号できない場合は None。"""

    @abstractmethod
    def add(self, credential: Credential) -> None: ...

    @abstractmethod
    def update(self, credential: Credential) -> None:
        """存在しない場合は CredentialNotFoundError。"""

    @abstractmethod
    def delete(self, credential_id: CredentialId) -> None: ...

    @abstractmethod
    def upsert_many(self, credentials: list[Credential]) -> None:
        """1トランザクションで追加または上書きする。"""
```

`src/infrastructure/database.py`

```python
import sqlite3

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS vault_meta (
  id             INTEGER PRIMARY KEY CHECK (id = 1),
  kdf_salt       BLOB    NOT NULL,
  kdf_n          INTEGER NOT NULL,
  kdf_r          INTEGER NOT NULL,
  kdf_p          INTEGER NOT NULL,
  verifier       BLOB    NOT NULL,
  schema_version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS credentials (
  id         TEXT PRIMARY KEY,
  payload    BLOB NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


def connect(path: str) -> sqlite3.Connection:
    # 鍵導出を別スレッドで行うため check_same_thread=False。書き込みは UI から逐次行う
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
```

`src/infrastructure/credential_codec.py`

```python
import json
from datetime import datetime

from domain.credential import Credential, CredentialId, Password, Title, Url
from domain.errors import ValidationError
from infrastructure.crypto import Cipher, DecryptionError

# 復号・JSON 解析・値オブジェクト検証のどれかで失敗したら「読めないデータ」として扱う
DECODE_ERRORS = (DecryptionError, ValueError, KeyError, TypeError, ValidationError)


def encrypt_credential(cipher: Cipher, credential: Credential) -> bytes:
    data = {
        "title": credential.title.value,
        "login_id": credential.login_id,
        "password": credential.password.value,
        "url": credential.url.value if credential.url else "",
        "memo": credential.memo,
    }
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return cipher.encrypt(plaintext, credential.id.value.encode("utf-8"))


def decrypt_credential(
    cipher: Cipher, credential_id: str, payload: bytes, created_at: str, updated_at: str
) -> Credential:
    data = json.loads(cipher.decrypt(payload, credential_id.encode("utf-8")).decode("utf-8"))
    return Credential(
        id=CredentialId(credential_id),
        title=Title(data["title"]),
        login_id=data["login_id"],
        password=Password(data["password"]),
        url=Url.parse(data["url"]),
        memo=data["memo"],
        created_at=datetime.fromisoformat(created_at),
        updated_at=datetime.fromisoformat(updated_at),
    )
```

`src/infrastructure/sqlite_repository.py`

```python
import sqlite3

from domain.credential import Credential, CredentialId
from domain.errors import CredentialNotFoundError
from domain.repository import CredentialList, CredentialRepository
from infrastructure.credential_codec import DECODE_ERRORS, decrypt_credential, encrypt_credential
from infrastructure.crypto import Cipher

_SELECT = "SELECT id, payload, created_at, updated_at FROM credentials"


class SqliteCredentialRepository(CredentialRepository):
    def __init__(self, conn: sqlite3.Connection, cipher: Cipher):
        self._conn = conn
        self._cipher = cipher

    def _decode(self, row: sqlite3.Row) -> Credential:
        return decrypt_credential(
            self._cipher, row["id"], row["payload"], row["created_at"], row["updated_at"]
        )

    def _row(self, credential: Credential) -> tuple:
        return (
            credential.id.value,
            encrypt_credential(self._cipher, credential),
            credential.created_at.isoformat(),
            credential.updated_at.isoformat(),
        )

    def list_all(self) -> CredentialList:
        items, unreadable = [], 0
        for row in self._conn.execute(_SELECT):
            try:
                items.append(self._decode(row))
            except DECODE_ERRORS:
                unreadable += 1
        return CredentialList(items, unreadable)

    def get(self, credential_id: CredentialId) -> Credential | None:
        row = self._conn.execute(_SELECT + " WHERE id = ?", (credential_id.value,)).fetchone()
        if row is None:
            return None
        try:
            return self._decode(row)
        except DECODE_ERRORS:
            return None

    def add(self, credential: Credential) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO credentials (id, payload, created_at, updated_at) VALUES (?, ?, ?, ?)",
                self._row(credential),
            )

    def update(self, credential: Credential) -> None:
        credential_id, payload, _, updated_at = self._row(credential)
        with self._conn:
            cursor = self._conn.execute(
                "UPDATE credentials SET payload = ?, updated_at = ? WHERE id = ?",
                (payload, updated_at, credential_id),
            )
        if cursor.rowcount == 0:
            raise CredentialNotFoundError()

    def delete(self, credential_id: CredentialId) -> None:
        with self._conn:
            self._conn.execute("DELETE FROM credentials WHERE id = ?", (credential_id.value,))

    def upsert_many(self, credentials: list[Credential]) -> None:
        with self._conn:
            self._conn.executemany(
                "INSERT INTO credentials (id, payload, created_at, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, "
                "created_at = excluded.created_at, updated_at = excluded.updated_at",
                [self._row(c) for c in credentials],
            )
```

- [ ] **Step 4: 通ることを確認**

Run: `Scripts/python -m pytest tests -v`
Expected: すべて PASS

---

### Task 5: Vault ストア（初期設定・解除・マスターPW変更・バックアップ入出力）

**Files:**
- Create: `src/application/errors.py`, `src/application/ports.py`, `src/infrastructure/sqlite_vault.py`
- Test: `tests/infrastructure/test_sqlite_vault.py`

**Interfaces:**
- Consumes: Task 3 の `KdfParams` / `derive_key` / `Cipher` / verifier、Task 4 の `connect` / `SCHEMA_VERSION` / codec / `SqliteCredentialRepository` / `CredentialRepository`
- Produces:
  - `application.errors`: `ApplicationError(message)`（`.message`）、`WrongMasterPasswordError()`, `TooManyAttemptsError(retry_after: float)`（`.retry_after`）, `VaultLockedError()`, `VaultStateError(message)`, `BackupFormatError(message)`, `CorruptedDataError(message)`
  - `application.ports.VaultStore`（Protocol）: `is_initialized() -> bool`, `initialize(master_password) -> CredentialRepository`, `open(master_password) -> CredentialRepository`, `change_master_password(current, new) -> CredentialRepository`, `export_backup() -> bytes`, `read_backup(data: bytes, master_password: str) -> list[Credential]`
  - `SqliteVault(conn, kdf_n: int = DEFAULT_KDF_N)` が上記を実装。`BACKUP_FORMAT = "passwordapp-backup"`, `BACKUP_VERSION = 1`

- [ ] **Step 1: 失敗するテストを書く** — `tests/infrastructure/test_sqlite_vault.py`

```python
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
```

注: パラメータ化したテストのうち `_tampered` を使うものは内部で `initialize` するので、未初期化の `conn` を使う（各テストで新しい `tmp_path`）。`read_backup` は Vault の初期化状態に依存しない。

- [ ] **Step 2: 失敗を確認**

Run: `Scripts/python -m pytest tests/infrastructure/test_sqlite_vault.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'application.errors'`）

- [ ] **Step 3: 実装**

`src/application/errors.py`

```python
import math


class ApplicationError(Exception):
    """ユースケースの失敗。message は画面にそのまま表示できる文言。"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class WrongMasterPasswordError(ApplicationError):
    def __init__(self):
        super().__init__("マスターパスワードが違います")


class TooManyAttemptsError(ApplicationError):
    def __init__(self, retry_after: float):
        super().__init__(f"続けて失敗したため、{math.ceil(retry_after)}秒後に再試行してください")
        self.retry_after = retry_after


class VaultLockedError(ApplicationError):
    def __init__(self):
        super().__init__("ロックされています")


class VaultStateError(ApplicationError):
    pass


class BackupFormatError(ApplicationError):
    pass


class CorruptedDataError(ApplicationError):
    pass
```

`src/application/ports.py`

```python
from typing import Protocol

from domain.credential import Credential
from domain.repository import CredentialRepository


class VaultStore(Protocol):
    """鍵の管理と暗号化データの保管を担う（インフラ層が実装する）。"""

    def is_initialized(self) -> bool: ...

    def initialize(self, master_password: str) -> CredentialRepository: ...

    def open(self, master_password: str) -> CredentialRepository:
        """パスワードが違う場合は WrongMasterPasswordError。"""

    def change_master_password(self, current: str, new: str) -> CredentialRepository: ...

    def export_backup(self) -> bytes: ...

    def read_backup(self, data: bytes, master_password: str) -> list[Credential]:
        """形式不正は BackupFormatError、パスワード違いは WrongMasterPasswordError。"""
```

`src/infrastructure/sqlite_vault.py`

```python
import base64
import json
import sqlite3

from application.errors import (
    BackupFormatError,
    CorruptedDataError,
    VaultStateError,
    WrongMasterPasswordError,
)
from domain.credential import Credential
from infrastructure.credential_codec import DECODE_ERRORS, decrypt_credential, encrypt_credential
from infrastructure.crypto import (
    DEFAULT_KDF_N,
    Cipher,
    KdfParams,
    check_verifier,
    derive_key,
    make_verifier,
)
from infrastructure.database import SCHEMA_VERSION
from infrastructure.sqlite_repository import SqliteCredentialRepository

BACKUP_FORMAT = "passwordapp-backup"
BACKUP_VERSION = 1

_SELECT_ROWS = "SELECT id, payload, created_at, updated_at FROM credentials"


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text, validate=True)


class SqliteVault:
    def __init__(self, conn: sqlite3.Connection, kdf_n: int = DEFAULT_KDF_N):
        self._conn = conn
        self._kdf_n = kdf_n

    # --- meta ---------------------------------------------------------------

    def _load_meta(self) -> tuple[KdfParams, bytes] | None:
        row = self._conn.execute(
            "SELECT kdf_salt, kdf_n, kdf_r, kdf_p, verifier FROM vault_meta WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        params = KdfParams(row["kdf_salt"], row["kdf_n"], row["kdf_r"], row["kdf_p"])
        return params, row["verifier"]

    def _require_meta(self) -> tuple[KdfParams, bytes]:
        meta = self._load_meta()
        if meta is None:
            raise VaultStateError("初期設定がされていません")
        return meta

    def _save_meta(self, params: KdfParams, verifier: bytes) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO vault_meta "
            "(id, kdf_salt, kdf_n, kdf_r, kdf_p, verifier, schema_version) "
            "VALUES (1, ?, ?, ?, ?, ?, ?)",
            (params.salt, params.n, params.r, params.p, verifier, SCHEMA_VERSION),
        )

    def _unlock_cipher(self, master_password: str) -> Cipher:
        params, verifier = self._require_meta()
        cipher = Cipher(derive_key(master_password, params))
        if not check_verifier(cipher, verifier):
            raise WrongMasterPasswordError()
        return cipher

    # --- VaultStore ---------------------------------------------------------

    def is_initialized(self) -> bool:
        return self._load_meta() is not None

    def initialize(self, master_password: str) -> SqliteCredentialRepository:
        if self.is_initialized():
            raise VaultStateError("すでに初期設定済みです")
        params = KdfParams.generate(n=self._kdf_n)
        cipher = Cipher(derive_key(master_password, params))
        with self._conn:
            self._save_meta(params, make_verifier(cipher))
        return SqliteCredentialRepository(self._conn, cipher)

    def open(self, master_password: str) -> SqliteCredentialRepository:
        return SqliteCredentialRepository(self._conn, self._unlock_cipher(master_password))

    def change_master_password(self, current: str, new: str) -> SqliteCredentialRepository:
        old_cipher = self._unlock_cipher(current)
        rows = self._conn.execute(_SELECT_ROWS).fetchall()
        try:
            credentials = [decrypt_credential(old_cipher, *tuple(row)) for row in rows]
        except DECODE_ERRORS as e:
            raise CorruptedDataError("読めないデータがあるため、マスターパスワードを変更できません") from e
        params = KdfParams.generate(n=self._kdf_n)
        new_cipher = Cipher(derive_key(new, params))
        with self._conn:
            self._save_meta(params, make_verifier(new_cipher))
            self._conn.executemany(
                "UPDATE credentials SET payload = ? WHERE id = ?",
                [(encrypt_credential(new_cipher, c), c.id.value) for c in credentials],
            )
        return SqliteCredentialRepository(self._conn, new_cipher)

    def export_backup(self) -> bytes:
        params, verifier = self._require_meta()
        doc = {
            "format": BACKUP_FORMAT,
            "version": BACKUP_VERSION,
            "kdf": {"salt": _b64e(params.salt), "n": params.n, "r": params.r, "p": params.p},
            "verifier": _b64e(verifier),
            "credentials": [
                {
                    "id": row["id"],
                    "payload": _b64e(row["payload"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in self._conn.execute(_SELECT_ROWS)
            ],
        }
        return json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")

    def read_backup(self, data: bytes, master_password: str) -> list[Credential]:
        try:
            doc = json.loads(data.decode("utf-8"))
            if doc["format"] != BACKUP_FORMAT or doc["version"] != BACKUP_VERSION:
                raise BackupFormatError("対応していないバックアップ形式です")
            kdf = doc["kdf"]
            params = KdfParams(_b64d(kdf["salt"]), kdf["n"], kdf["r"], kdf["p"])
            verifier = _b64d(doc["verifier"])
            rows = [
                (r["id"], _b64d(r["payload"]), r["created_at"], r["updated_at"])
                for r in doc["credentials"]
            ]
        except BackupFormatError:
            raise
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise BackupFormatError("バックアップファイルの形式が正しくありません") from e
        cipher = Cipher(derive_key(master_password, params))
        if not check_verifier(cipher, verifier):
            raise WrongMasterPasswordError()
        try:
            return [decrypt_credential(cipher, *row) for row in rows]
        except DECODE_ERRORS as e:
            raise BackupFormatError("バックアップに壊れたデータが含まれています") from e
```

注: `doc` が `list`（`b"[]"`）の場合 `doc["format"]` は `TypeError` になり `BackupFormatError` に変換される。

- [ ] **Step 4: 通ることを確認**

Run: `Scripts/python -m pytest tests -v`
Expected: すべて PASS

---

### Task 6: ユースケース（VaultService・CredentialService）

**Files:**
- Create: `src/application/vault_service.py`, `src/application/credential_service.py`
- Test: `tests/application/test_vault_service.py`, `tests/application/test_credential_service.py`

**Interfaces:**
- Consumes: `VaultStore`, `application.errors`（Task 5）、`SqliteVault` / `connect`（テストのみ）、`Credential` / `CredentialList` / `ValidationError` / `CredentialNotFoundError`
- Produces:
  - `MIN_MASTER_LENGTH = 8`, `MAX_FAILURES = 5`, `LOCKOUT_SECONDS = 30.0`
  - `VaultService(store: VaultStore, clock: Callable[[], float] = time.monotonic)`: `is_initialized() -> bool`, `is_unlocked: bool`（property）, `setup(master, confirm)`, `unlock(master)`, `lock()`, `repository() -> CredentialRepository`（ロック中は `VaultLockedError`）, `change_master_password(current, new, confirm)`
  - マスターPW の検証エラー: `ValidationError("master", ...)` / `ValidationError("confirm", ...)`
  - `CredentialInput(title: str, login_id: str, password: str, url: str, memo: str)`
  - `CredentialService(vault: VaultService)`: `search(query: str = "") -> CredentialList`（タイトルの大文字小文字を無視した昇順）, `add(data) -> Credential`, `edit(credential_id: str, data) -> Credential`, `delete(credential_id: str) -> None`

- [ ] **Step 1: 失敗するテストを書く** — `tests/application/test_vault_service.py`

```python
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
```

`tests/application/test_credential_service.py`

```python
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
```

- [ ] **Step 2: 失敗を確認**

Run: `Scripts/python -m pytest tests/application -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 実装**

`src/application/vault_service.py`

```python
import time
from typing import Callable

from application.errors import TooManyAttemptsError, VaultLockedError, WrongMasterPasswordError
from application.ports import VaultStore
from domain.errors import ValidationError
from domain.repository import CredentialRepository

MIN_MASTER_LENGTH = 8
MAX_FAILURES = 5
LOCKOUT_SECONDS = 30.0


def _validate_new_master(master: str, confirm: str) -> None:
    if len(master) < MIN_MASTER_LENGTH:
        raise ValidationError("master", f"マスターパスワードは{MIN_MASTER_LENGTH}文字以上にしてください")
    if master != confirm:
        raise ValidationError("confirm", "確認用のパスワードが一致しません")


class VaultService:
    def __init__(self, store: VaultStore, clock: Callable[[], float] = time.monotonic):
        self._store = store
        self._clock = clock
        self._repository: CredentialRepository | None = None
        self._failures = 0
        self._locked_until = 0.0

    def is_initialized(self) -> bool:
        return self._store.is_initialized()

    @property
    def is_unlocked(self) -> bool:
        return self._repository is not None

    def setup(self, master: str, confirm: str) -> None:
        _validate_new_master(master, confirm)
        self._repository = self._store.initialize(master)

    def unlock(self, master: str) -> None:
        now = self._clock()
        if now < self._locked_until:
            raise TooManyAttemptsError(self._locked_until - now)
        try:
            self._repository = self._store.open(master)
        except WrongMasterPasswordError:
            self._failures += 1
            if self._failures >= MAX_FAILURES:
                self._failures = 0
                self._locked_until = now + LOCKOUT_SECONDS
            raise
        self._failures = 0

    def lock(self) -> None:
        # 鍵を持つリポジトリへの参照を捨てる（Python ではメモリの確実な消去はできない）
        self._repository = None

    def repository(self) -> CredentialRepository:
        if self._repository is None:
            raise VaultLockedError()
        return self._repository

    def change_master_password(self, current: str, new: str, confirm: str) -> None:
        self.repository()
        _validate_new_master(new, confirm)
        self._repository = self._store.change_master_password(current, new)
```

`src/application/credential_service.py`

```python
from dataclasses import dataclass

from application.vault_service import VaultService
from domain.credential import Credential, CredentialId
from domain.errors import CredentialNotFoundError
from domain.repository import CredentialList


@dataclass(frozen=True)
class CredentialInput:
    title: str
    login_id: str
    password: str
    url: str
    memo: str


class CredentialService:
    def __init__(self, vault: VaultService):
        self._vault = vault

    def search(self, query: str = "") -> CredentialList:
        result = self._vault.repository().list_all()
        items = sorted(
            (c for c in result.items if c.matches(query)),
            key=lambda c: c.title.value.casefold(),
        )
        return CredentialList(items, result.unreadable)

    def add(self, data: CredentialInput) -> Credential:
        credential = Credential.create(data.title, data.login_id, data.password, data.url, data.memo)
        self._vault.repository().add(credential)
        return credential

    def edit(self, credential_id: str, data: CredentialInput) -> Credential:
        repository = self._vault.repository()
        credential = repository.get(CredentialId(credential_id))
        if credential is None:
            raise CredentialNotFoundError()
        credential.update(data.title, data.login_id, data.password, data.url, data.memo)
        repository.update(credential)
        return credential

    def delete(self, credential_id: str) -> None:
        self._vault.repository().delete(CredentialId(credential_id))
```

- [ ] **Step 4: 通ることを確認**

Run: `Scripts/python -m pytest tests -v`
Expected: すべて PASS

---

### Task 7: バックアップのユースケース（BackupService）

**Files:**
- Create: `src/application/backup_service.py`
- Test: `tests/application/test_backup_service.py`

**Interfaces:**
- Consumes: `VaultService`（Task 6）、`VaultStore.export_backup / read_backup`（Task 5）、`CredentialRepository.get / upsert_many`（Task 4）
- Produces: `ImportResult(added: int, updated: int, skipped: int)`, `BackupService(vault: VaultService, store: VaultStore)`: `export_backup() -> bytes`, `import_backup(data: bytes, backup_master: str) -> ImportResult`, `BackupService.default_file_name(today: date) -> str`

- [ ] **Step 1: 失敗するテストを書く** — `tests/application/test_backup_service.py`

```python
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
```

- [ ] **Step 2: 失敗を確認**

Run: `Scripts/python -m pytest tests/application/test_backup_service.py -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: 実装** — `src/application/backup_service.py`

```python
from dataclasses import dataclass
from datetime import date

from application.ports import VaultStore
from application.vault_service import VaultService


@dataclass(frozen=True)
class ImportResult:
    added: int
    updated: int
    skipped: int


class BackupService:
    def __init__(self, vault: VaultService, store: VaultStore):
        self._vault = vault
        self._store = store

    @staticmethod
    def default_file_name(today: date) -> str:
        return f"passwordapp-backup-{today:%Y%m%d}.json"

    def export_backup(self) -> bytes:
        self._vault.repository()  # ロック中は書き出させない
        return self._store.export_backup()

    def import_backup(self, data: bytes, backup_master: str) -> ImportResult:
        repository = self._vault.repository()
        # 全件の復号に成功してから書き込む（途中で失敗したら何も書き込まない）
        incoming = self._store.read_backup(data, backup_master)
        to_save, added, updated, skipped = [], 0, 0, 0
        for credential in incoming:
            existing = repository.get(credential.id)
            if existing is None:
                added += 1
                to_save.append(credential)
            elif credential.updated_at > existing.updated_at:
                updated += 1
                to_save.append(credential)
            else:
                skipped += 1
        repository.upsert_many(to_save)
        return ImportResult(added, updated, skipped)
```

- [ ] **Step 4: 通ることを確認**

Run: `Scripts/python -m pytest tests -v`
Expected: すべて PASS

---

### Task 8: 画面の土台（自動ロック・クリップボード・初期設定／解除画面・main）

**Files:**
- Create: `src/presentation/session_guard.py`, `src/presentation/app.py`, `src/presentation/views/lock_views.py`
- Modify: `src/main.py`（全面置き換え）
- Test: `tests/presentation/test_session_guard.py`

**Interfaces:**
- Consumes: `VaultService` / `CredentialService` / `BackupService`（Task 6・7）、`PasswordGenerator`（Task 2）、`SqliteVault` / `connect`（Task 4・5）、`DomainError` / `ApplicationError`
- Produces:
  - `AutoLock(idle_timeout: float = 300.0, clock=time.monotonic)`: `touch()`, `suspended()`（context manager）, `should_lock_on_background() -> bool`, `idle_expired() -> bool`
  - `ClipboardCleaner(clipboard, delay: float = 30.0, sleep=asyncio.sleep)`: `async copy(value: str)`, `async wait()`（テスト用）
  - `Screen(content: ft.Control, appbar: ft.AppBar | None = None, fab: ft.FloatingActionButton | None = None)`
  - `PasswordApp(page, vault, credentials, backup, generator)`: 属性 `page, vault, credentials, backup, generator, auto_lock, file_picker`; メソッド `start()`, `show(screen)`, `show_start()`, `show_unlock()`, `show_list()`, `show_edit(credential=None)`, `show_generator()`, `show_settings()`, `lock()`, `action(handler) -> async handler`, `notify(message)`, `async copy(value, label)`, `confirm(title, message, on_yes)`
  - `setup_screen(app) -> Screen`, `unlock_screen(app) -> Screen`（`lock_views.py`）
  - UI テスト用キー: `setup_master`, `setup_confirm`, `setup_submit`, `unlock_master`, `unlock_submit`

- [ ] **Step 1: 失敗するテストを書く** — `tests/presentation/test_session_guard.py`

```python
import asyncio

from presentation.session_guard import AutoLock, ClipboardCleaner


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeClipboard:
    def __init__(self):
        self.value = None

    async def set(self, value):
        self.value = value

    async def get(self):
        return self.value


def test_idle_expires_after_timeout_and_touch_resets():
    clock = FakeClock()
    lock = AutoLock(idle_timeout=300, clock=clock)
    clock.now = 299
    assert not lock.idle_expired()
    lock.touch()
    clock.now = 598
    assert not lock.idle_expired()
    clock.now = 599
    assert lock.idle_expired()


def test_suspended_blocks_background_lock_and_idle():
    clock = FakeClock()
    lock = AutoLock(idle_timeout=300, clock=clock)
    assert lock.should_lock_on_background()
    with lock.suspended():
        clock.now = 1000
        assert not lock.should_lock_on_background()
        assert not lock.idle_expired()
    # ファイル選択から戻った直後は無操作時間をリセットする
    assert lock.should_lock_on_background()
    assert not lock.idle_expired()


async def test_clipboard_is_cleared_after_delay():
    clipboard = FakeClipboard()

    async def no_wait(_):
        pass

    cleaner = ClipboardCleaner(clipboard, sleep=no_wait)
    await cleaner.copy("secret")
    assert clipboard.value == "secret"
    await cleaner.wait()
    assert clipboard.value == ""


async def test_clipboard_is_kept_if_user_copied_something_else():
    clipboard = FakeClipboard()
    gate = asyncio.Event()

    async def wait_gate(_):
        await gate.wait()

    cleaner = ClipboardCleaner(clipboard, sleep=wait_gate)
    await cleaner.copy("secret")
    clipboard.value = "other text"
    gate.set()
    await cleaner.wait()
    assert clipboard.value == "other text"


async def test_second_copy_cancels_first_timer():
    clipboard = FakeClipboard()
    gate = asyncio.Event()

    async def wait_gate(_):
        await gate.wait()

    cleaner = ClipboardCleaner(clipboard, sleep=wait_gate)
    await cleaner.copy("first")
    first = cleaner._task
    await cleaner.copy("second")
    await asyncio.sleep(0)
    assert first.cancelled()
    gate.set()
    await cleaner.wait()
    assert clipboard.value == ""
```

- [ ] **Step 2: 失敗を確認**

Run: `Scripts/python -m pytest tests/presentation -v`
Expected: FAIL（`ModuleNotFoundError`）

- [ ] **Step 3: session_guard を実装** — `src/presentation/session_guard.py`

```python
import asyncio
import time
from contextlib import contextmanager
from typing import Awaitable, Callable, Protocol

IDLE_TIMEOUT_SECONDS = 300.0
CLIPBOARD_CLEAR_SECONDS = 30.0


class AutoLock:
    """無操作時間と、外部画面（ファイル選択など）を開いている状態を管理する。"""

    def __init__(self, idle_timeout: float = IDLE_TIMEOUT_SECONDS, clock: Callable[[], float] = time.monotonic):
        self._idle_timeout = idle_timeout
        self._clock = clock
        self._last_activity = clock()
        self._suspended = 0

    def touch(self) -> None:
        self._last_activity = self._clock()

    @contextmanager
    def suspended(self):
        self._suspended += 1
        try:
            yield
        finally:
            self._suspended -= 1
            self.touch()

    def should_lock_on_background(self) -> bool:
        return self._suspended == 0

    def idle_expired(self) -> bool:
        return self._suspended == 0 and self._clock() - self._last_activity >= self._idle_timeout


class ClipboardPort(Protocol):
    async def set(self, value: str) -> None: ...

    async def get(self) -> str | None: ...


class ClipboardCleaner:
    """コピーした値を一定時間後に消す。別の内容に変わっていたら触らない。"""

    def __init__(
        self,
        clipboard: ClipboardPort,
        delay: float = CLIPBOARD_CLEAR_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._clipboard = clipboard
        self._delay = delay
        self._sleep = sleep
        self._task: asyncio.Task | None = None

    async def copy(self, value: str) -> None:
        await self._clipboard.set(value)
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = asyncio.create_task(self._clear_later(value))

    async def _clear_later(self, value: str) -> None:
        await self._sleep(self._delay)
        try:
            if await self._clipboard.get() == value:
                await self._clipboard.set("")
        except Exception:
            pass  # クリップボードが使えない状態（アプリ終了中など）では何もしない

    async def wait(self) -> None:
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
```

- [ ] **Step 4: テストが通ることを確認**

Run: `Scripts/python -m pytest tests/presentation -v`
Expected: すべて PASS

- [ ] **Step 5: アプリ本体を実装** — `src/presentation/app.py`

```python
import asyncio
import inspect
import sqlite3
from dataclasses import dataclass

import flet as ft

from application.backup_service import BackupService
from application.credential_service import CredentialService
from application.errors import ApplicationError
from application.vault_service import VaultService
from domain.credential import Credential
from domain.errors import DomainError
from domain.password_generator import PasswordGenerator
from presentation.session_guard import CLIPBOARD_CLEAR_SECONDS, AutoLock, ClipboardCleaner

IDLE_CHECK_INTERVAL_SECONDS = 10
BACKGROUND_STATES = (ft.AppLifecycleState.HIDE, ft.AppLifecycleState.PAUSE)


@dataclass
class Screen:
    content: ft.Control
    appbar: ft.AppBar | None = None
    fab: ft.FloatingActionButton | None = None


class PasswordApp:
    def __init__(
        self,
        page: ft.Page,
        vault: VaultService,
        credentials: CredentialService,
        backup: BackupService,
        generator: PasswordGenerator,
    ):
        self.page = page
        self.vault = vault
        self.credentials = credentials
        self.backup = backup
        self.generator = generator
        self.auto_lock = AutoLock()
        # Flet のサービスは強参照がないと解除されるので、このオブジェクトで保持する
        self.clipboard = ft.Clipboard()
        self.file_picker = ft.FilePicker()
        self._clipboard_cleaner = ClipboardCleaner(self.clipboard)

    def start(self) -> None:
        self.page.title = "パスワード管理"
        self.page.on_app_lifecycle_state_change = self._on_lifecycle
        self.page.run_task(self._watch_idle)
        self.show_start()

    # --- 画面切替 -------------------------------------------------------------

    def show(self, screen: Screen) -> None:
        self.auto_lock.touch()
        self.page.appbar = screen.appbar
        self.page.floating_action_button = screen.fab
        self.page.controls.clear()
        self.page.controls.append(ft.SafeArea(expand=True, content=screen.content))
        self.page.update()

    def show_start(self) -> None:
        from presentation.views.lock_views import setup_screen, unlock_screen

        self.show(unlock_screen(self) if self.vault.is_initialized() else setup_screen(self))

    def show_unlock(self) -> None:
        from presentation.views.lock_views import unlock_screen

        self.show(unlock_screen(self))

    def show_list(self) -> None:
        from presentation.views.list_view import list_screen

        self.show(list_screen(self))

    def show_edit(self, credential: Credential | None = None) -> None:
        from presentation.views.edit_view import edit_screen

        self.show(edit_screen(self, credential))

    def show_generator(self) -> None:
        from presentation.views.generator_view import generator_screen

        self.show(generator_screen(self))

    def show_settings(self) -> None:
        from presentation.views.settings_view import settings_screen

        self.show(settings_screen(self))

    # --- ロック ---------------------------------------------------------------

    def lock(self) -> None:
        if not self.vault.is_unlocked:
            return
        self.vault.lock()
        self.page.pop_dialog()
        self.show_unlock()

    async def _on_lifecycle(self, e: ft.AppLifecycleStateChangeEvent) -> None:
        if e.state in BACKGROUND_STATES and self.auto_lock.should_lock_on_background():
            self.lock()

    async def _watch_idle(self) -> None:
        while True:
            await asyncio.sleep(IDLE_CHECK_INTERVAL_SECONDS)
            if self.vault.is_unlocked and self.auto_lock.idle_expired():
                self.lock()

    # --- 共通の操作 -----------------------------------------------------------

    def action(self, handler):
        """イベントハンドラを包む: 操作時刻の記録と、想定内エラーの表示。"""

        async def wrapped(e):
            self.auto_lock.touch()
            try:
                result = handler(e)
                if inspect.isawaitable(result):
                    await result
            except (DomainError, ApplicationError) as err:
                self.notify(err.message)
            except sqlite3.Error:
                self.notify("データの保存・読み込みに失敗しました")

        return wrapped

    def notify(self, message: str) -> None:
        self.page.show_dialog(ft.SnackBar(ft.Text(message)))

    async def copy(self, value: str, label: str) -> None:
        await self._clipboard_cleaner.copy(value)
        self.notify(f"{label}をコピーしました（{int(CLIPBOARD_CLEAR_SECONDS)}秒後に消去）")

    def confirm(self, title: str, message: str, on_yes) -> None:
        def yes(e):
            self.page.pop_dialog()
            on_yes()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton(content="キャンセル", on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton(content="削除", on_click=self.action(yes)),
            ],
        )
        self.page.show_dialog(dialog)
```

- [ ] **Step 6: 初期設定・解除画面を実装** — `src/presentation/views/lock_views.py`

```python
import asyncio
from typing import TYPE_CHECKING

import flet as ft

from application.errors import ApplicationError
from domain.errors import ValidationError

if TYPE_CHECKING:
    from presentation.app import PasswordApp, Screen


def _password_field(label: str, key: str, autofocus: bool = False) -> ft.TextField:
    return ft.TextField(label=label, password=True, can_reveal_password=True, autofocus=autofocus, key=key)


def _layout(*controls: ft.Control) -> ft.Control:
    return ft.Container(
        padding=24,
        content=ft.Column(list(controls), spacing=16, scroll=ft.ScrollMode.AUTO),
    )


def setup_screen(app: "PasswordApp") -> "Screen":
    from presentation.app import Screen

    master = _password_field("マスターパスワード（8文字以上）", "setup_master", autofocus=True)
    confirm = _password_field("確認のためもう一度入力", "setup_confirm")
    progress = ft.ProgressRing(visible=False, width=20, height=20)

    async def create(e):
        master.error = confirm.error = None
        progress.visible = True
        app.page.update()
        try:
            await asyncio.to_thread(app.vault.setup, master.value, confirm.value)
        except ValidationError as err:
            (confirm if err.field == "confirm" else master).error = err.message
            return
        finally:
            progress.visible = False
        app.show_list()

    return Screen(
        _layout(
            ft.Text("はじめに", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("マスターパスワードを決めてください。忘れるとデータは復元できません。"),
            master,
            confirm,
            ft.Row([ft.FilledButton(content="作成", on_click=app.action(create), key="setup_submit"), progress]),
        )
    )


def unlock_screen(app: "PasswordApp") -> "Screen":
    from presentation.app import Screen

    master = _password_field("マスターパスワード", "unlock_master", autofocus=True)
    progress = ft.ProgressRing(visible=False, width=20, height=20)

    async def unlock(e):
        master.error = None
        progress.visible = True
        app.page.update()
        try:
            await asyncio.to_thread(app.vault.unlock, master.value)
        except ApplicationError as err:
            master.error = err.message
            master.value = ""
            return
        finally:
            progress.visible = False
        app.show_list()

    master.on_submit = app.action(unlock)
    return Screen(
        _layout(
            ft.Text("ロック中", size=24, weight=ft.FontWeight.BOLD),
            master,
            ft.Row([ft.FilledButton(content="開く", on_click=app.action(unlock), key="unlock_submit"), progress]),
        )
    )
```

- [ ] **Step 7: main.py を置き換え** — `src/main.py`

```python
import os
from pathlib import Path

import flet as ft

from application.backup_service import BackupService
from application.credential_service import CredentialService
from application.vault_service import VaultService
from domain.password_generator import PasswordGenerator
from infrastructure.database import connect
from infrastructure.sqlite_vault import SqliteVault
from presentation.app import PasswordApp


def database_path() -> str:
    base = Path(os.environ.get("FLET_APP_STORAGE_DATA") or Path.home() / ".passwordapp")
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "vault.db")


def main(page: ft.Page):
    store = SqliteVault(connect(database_path()))
    vault = VaultService(store)
    PasswordApp(
        page,
        vault=vault,
        credentials=CredentialService(vault),
        backup=BackupService(vault, store),
        generator=PasswordGenerator(),
    ).start()


if __name__ == "__main__":
    ft.run(main)
```

- [ ] **Step 8: 一時的なスタブを置いて起動確認**

一覧画面は Task 9 で作るので、この時点では `src/presentation/views/list_view.py` に仮実装を置く（Task 9 で全面置き換え）:

```python
import flet as ft


def list_screen(app):
    from presentation.app import Screen

    return Screen(ft.Text("一覧（Task 9 で実装）"))
```

Run: `Scripts/python -m pytest tests -v`
Expected: すべて PASS

Run: `Scripts/python -c "import sys; sys.path.insert(0, 'src'); import main"`
Expected: エラーなし（import が通る）

Run（手動）: `Scripts/flet run src/main.py`
Expected: 初期設定画面が出る → 7文字で「作成」するとエラー表示 → 8文字以上＋一致で仮の一覧画面。ウィンドウを閉じて再度起動するとロック解除画面が出て、間違ったパスワードでエラー、正しいパスワードで仮の一覧に進む。確認後、`~/.passwordapp/vault.db` を削除して元に戻す。

---

### Task 9: 一覧・編集・パスワード生成の画面

**Files:**
- Modify: `src/presentation/views/list_view.py`（仮実装を全面置き換え）
- Create: `src/presentation/views/edit_view.py`, `src/presentation/views/generator_view.py`

**Interfaces:**
- Consumes: `PasswordApp` / `Screen`（Task 8）、`CredentialService` / `CredentialInput`（Task 6）、`GeneratorOptions` / `MIN_LENGTH` / `MAX_LENGTH` / `DEFAULT_LENGTH`（Task 2）
- Produces: `list_screen(app) -> Screen`, `edit_screen(app, credential: Credential | None) -> Screen`, `generator_screen(app) -> Screen`, `open_generator_dialog(app, on_use: Callable[[str], None]) -> None`, `generator_panel(app) -> tuple[ft.Control, Callable[[], str]]`
- UI テスト用キー: `search`, `add`, `edit_title`, `edit_login_id`, `edit_password`, `edit_url`, `edit_memo`, `edit_save`

- [ ] **Step 1: 一覧画面** — `src/presentation/views/list_view.py`

```python
from typing import TYPE_CHECKING

import flet as ft

from domain.credential import Credential

if TYPE_CHECKING:
    from presentation.app import PasswordApp, Screen


def _tile(app: "PasswordApp", credential: Credential) -> ft.ListTile:
    async def copy_id(e):
        await app.copy(credential.login_id, "ID")

    async def copy_password(e):
        await app.copy(credential.password.value, "パスワード")

    return ft.ListTile(
        title=credential.title.value,
        subtitle=credential.login_id or None,
        on_click=app.action(lambda e: app.show_edit(credential)),
        trailing=ft.Row(
            tight=True,
            controls=[
                ft.IconButton(
                    icon=ft.Icons.PERSON,
                    tooltip="IDをコピー",
                    disabled=not credential.login_id,
                    on_click=app.action(copy_id),
                ),
                ft.IconButton(icon=ft.Icons.KEY, tooltip="パスワードをコピー", on_click=app.action(copy_password)),
            ],
        ),
    )


def list_screen(app: "PasswordApp") -> "Screen":
    from presentation.app import Screen

    search = ft.TextField(hint_text="検索（タイトル・ID・URL・メモ）", prefix_icon=ft.Icons.SEARCH, key="search")
    notice = ft.Text(color=ft.Colors.ERROR, visible=False)
    items = ft.ListView(expand=True)

    def refresh():
        result = app.credentials.search(search.value)
        notice.value = f"読めないデータが {result.unreadable} 件あります"
        notice.visible = result.unreadable > 0
        if result.items:
            items.controls = [_tile(app, c) for c in result.items]
        else:
            empty = "見つかりません" if search.value.strip() else "まだ登録がありません。＋ボタンで追加してください"
            items.controls = [ft.Container(ft.Text(empty), padding=16)]

    search.on_change = app.action(lambda e: refresh())
    refresh()

    appbar = ft.AppBar(
        title=ft.Text("パスワード"),
        actions=[
            ft.IconButton(icon=ft.Icons.PASSWORD, tooltip="パスワード生成", on_click=app.action(lambda e: app.show_generator())),
            ft.IconButton(icon=ft.Icons.SETTINGS, tooltip="設定", on_click=app.action(lambda e: app.show_settings())),
            ft.IconButton(icon=ft.Icons.LOCK, tooltip="ロック", on_click=app.action(lambda e: app.lock())),
        ],
    )
    fab = ft.FloatingActionButton(icon=ft.Icons.ADD, tooltip="追加", key="add", on_click=app.action(lambda e: app.show_edit()))
    content = ft.Column(
        expand=True,
        controls=[ft.Container(search, padding=ft.Padding.symmetric(horizontal=16, vertical=8)), notice, items],
    )
    return Screen(content, appbar, fab)
```

- [ ] **Step 2: 生成パネル・生成画面・生成ダイアログ** — `src/presentation/views/generator_view.py`

```python
from typing import TYPE_CHECKING, Callable

import flet as ft

from domain.errors import ValidationError
from domain.password_generator import DEFAULT_LENGTH, MAX_LENGTH, MIN_LENGTH, GeneratorOptions

if TYPE_CHECKING:
    from presentation.app import PasswordApp, Screen

KINDS = (
    ("lowercase", "小文字 a-z"),
    ("uppercase", "大文字 A-Z"),
    ("digits", "数字 0-9"),
    ("symbols", "記号 !@#…"),
)


def generator_panel(app: "PasswordApp") -> tuple[ft.Control, Callable[[], str]]:
    state = {"value": ""}
    result = ft.Text(size=20, selectable=True, font_family="monospace")
    error = ft.Text(color=ft.Colors.ERROR, visible=False)
    length_label = ft.Text()
    length = ft.Slider(min=MIN_LENGTH, max=MAX_LENGTH, divisions=MAX_LENGTH - MIN_LENGTH, value=DEFAULT_LENGTH)
    checks = {name: ft.Checkbox(label=label, value=True) for name, label in KINDS}

    def regenerate():
        options = GeneratorOptions(
            length=int(length.value), **{name: bool(box.value) for name, box in checks.items()}
        )
        length_label.value = f"長さ: {options.length}"
        try:
            state["value"] = app.generator.generate(options)
            error.visible = False
        except ValidationError as err:
            state["value"] = ""
            error.value = err.message
            error.visible = True
        result.value = state["value"]

    handler = app.action(lambda e: regenerate())
    length.on_change = handler
    for box in checks.values():
        box.on_change = handler
    regenerate()

    panel = ft.Column(
        tight=True,
        controls=[
            result,
            error,
            length_label,
            length,
            *checks.values(),
            ft.TextButton(content="作り直す", icon=ft.Icons.REFRESH, on_click=handler),
        ],
    )
    return panel, lambda: state["value"]


def generator_screen(app: "PasswordApp") -> "Screen":
    from presentation.app import Screen

    panel, current = generator_panel(app)

    async def copy(e):
        if current():
            await app.copy(current(), "パスワード")

    appbar = ft.AppBar(
        leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="戻る", on_click=app.action(lambda e: app.show_list())),
        title=ft.Text("パスワード生成"),
    )
    content = ft.Container(
        padding=16,
        content=ft.Column(
            scroll=ft.ScrollMode.AUTO,
            controls=[panel, ft.FilledButton(content="コピー", icon=ft.Icons.CONTENT_COPY, on_click=app.action(copy))],
        ),
    )
    return Screen(content, appbar)


def open_generator_dialog(app: "PasswordApp", on_use: Callable[[str], None]) -> None:
    panel, current = generator_panel(app)

    def use(e):
        value = current()
        app.page.pop_dialog()
        if value:
            on_use(value)

    dialog = ft.AlertDialog(
        title=ft.Text("パスワード生成"),
        content=panel,
        actions=[
            ft.TextButton(content="キャンセル", on_click=lambda e: app.page.pop_dialog()),
            ft.FilledButton(content="使う", on_click=app.action(use)),
        ],
    )
    app.page.show_dialog(dialog)
```

- [ ] **Step 3: 登録・編集画面** — `src/presentation/views/edit_view.py`

```python
from typing import TYPE_CHECKING

import flet as ft

from application.credential_service import CredentialInput
from domain.credential import Credential
from domain.errors import ValidationError
from presentation.views.generator_view import open_generator_dialog

if TYPE_CHECKING:
    from presentation.app import PasswordApp, Screen


def edit_screen(app: "PasswordApp", credential: Credential | None) -> "Screen":
    from presentation.app import Screen

    is_new = credential is None
    title = ft.TextField(label="タイトル *", key="edit_title")
    login_id = ft.TextField(label="ID", key="edit_login_id")
    password = ft.TextField(label="パスワード *", password=True, can_reveal_password=True, expand=True, key="edit_password")
    url = ft.TextField(label="URL", hint_text="https://", keyboard_type=ft.KeyboardType.URL, key="edit_url")
    memo = ft.TextField(label="メモ", multiline=True, min_lines=3, max_lines=8, key="edit_memo")
    fields = {"title": title, "login_id": login_id, "password": password, "url": url, "memo": memo}

    if credential is not None:
        title.value = credential.title.value
        login_id.value = credential.login_id
        password.value = credential.password.value
        url.value = credential.url.value if credential.url else ""
        memo.value = credential.memo

    def use_generated(value: str):
        password.value = value
        app.page.update()

    def save(e):
        for field in fields.values():
            field.error = None
        data = CredentialInput(title.value, login_id.value, password.value, url.value, memo.value)
        try:
            if is_new:
                app.credentials.add(data)
            else:
                app.credentials.edit(credential.id.value, data)
        except ValidationError as err:
            fields[err.field].error = err.message
            return
        app.notify("保存しました")
        app.show_list()

    def delete():
        app.credentials.delete(credential.id.value)
        app.notify("削除しました")
        app.show_list()

    def ask_delete(e):
        app.confirm("削除しますか？", f"「{credential.title.value}」を削除します。元に戻せません。", delete)

    actions = [] if is_new else [ft.IconButton(icon=ft.Icons.DELETE, tooltip="削除", on_click=app.action(ask_delete))]
    appbar = ft.AppBar(
        leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="戻る", on_click=app.action(lambda e: app.show_list())),
        title=ft.Text("新規登録" if is_new else "編集"),
        actions=actions,
    )
    generate = ft.IconButton(
        icon=ft.Icons.AUTO_AWESOME,
        tooltip="パスワードを生成",
        on_click=app.action(lambda e: open_generator_dialog(app, use_generated)),
    )
    content = ft.Container(
        padding=16,
        content=ft.Column(
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                title,
                login_id,
                ft.Row([password, generate]),
                url,
                memo,
                ft.FilledButton(content="保存", icon=ft.Icons.SAVE, on_click=app.action(save), key="edit_save"),
            ],
        ),
    )
    return Screen(content, appbar)
```

- [ ] **Step 4: テストと起動確認**

Run: `Scripts/python -m pytest tests -v`
Expected: すべて PASS

Run（手動）: `Scripts/flet run src/main.py`
Expected（手動チェック）:
- ＋ → タイトル空で保存 → 「タイトルを入力してください」がタイトル欄に出る
- URL に `example.com` → URL 欄にエラー
- 生成ボタン → ダイアログで長さ・文字種を変えると作り直される／全部外すと「文字の種類を1つ以上…」→「使う」でパスワード欄に入る
- 保存 → 一覧に出る。3件ほど登録して、タイトル順に並ぶこと、検索で絞り込めること、大文字小文字を無視すること
- 鍵アイコン → 「パスワードをコピーしました」→ 30秒後に貼り付けると空（途中で別の文字列をコピーした場合はその文字列が残る）
- 行をタップ → 編集・保存、ゴミ箱 → 確認ダイアログ → 削除
- 一覧の鍵（ロック）ボタン → ロック解除画面へ

---

### Task 10: 設定画面（マスターパスワード変更・バックアップ）

**Files:**
- Create: `src/presentation/views/settings_view.py`

**Interfaces:**
- Consumes: `PasswordApp.file_picker` / `auto_lock.suspended()` / `notify` / `action`（Task 8）、`VaultService.change_master_password`（Task 6）、`BackupService.export_backup / import_backup / default_file_name`（Task 7）、`WrongMasterPasswordError` / `BackupFormatError`（Task 5）
- Produces: `settings_screen(app) -> Screen`

- [ ] **Step 1: 実装** — `src/presentation/views/settings_view.py`

```python
import asyncio
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import flet as ft

from application.backup_service import BackupService
from application.errors import ApplicationError, WrongMasterPasswordError
from domain.errors import ValidationError

if TYPE_CHECKING:
    from presentation.app import PasswordApp, Screen


def _password_field(label: str) -> ft.TextField:
    return ft.TextField(label=label, password=True, can_reveal_password=True)


def _ask_backup_password(app: "PasswordApp", data: bytes) -> None:
    field = ft.TextField(
        label="バックアップ作成時のマスターパスワード", password=True, can_reveal_password=True, autofocus=True
    )

    async def run(e):
        field.error = None
        try:
            result = await asyncio.to_thread(app.backup.import_backup, data, field.value)
        except ApplicationError as err:  # パスワード違い・形式不正はダイアログ内に表示
            field.error = err.message
            return
        app.page.pop_dialog()
        app.notify(f"追加 {result.added}件 / 更新 {result.updated}件 / スキップ {result.skipped}件")

    app.page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("バックアップを読み込む"),
            content=field,
            actions=[
                ft.TextButton(content="キャンセル", on_click=lambda e: app.page.pop_dialog()),
                ft.FilledButton(content="読み込む", on_click=app.action(run)),
            ],
        )
    )


def settings_screen(app: "PasswordApp") -> "Screen":
    from presentation.app import Screen

    current = _password_field("現在のマスターパスワード")
    new = _password_field("新しいマスターパスワード（8文字以上）")
    confirm = _password_field("新しいマスターパスワード（確認）")
    progress = ft.ProgressRing(visible=False, width=20, height=20)

    async def change(e):
        for field in (current, new, confirm):
            field.error = None
        progress.visible = True
        app.page.update()
        try:
            await asyncio.to_thread(app.vault.change_master_password, current.value, new.value, confirm.value)
        except ValidationError as err:
            (confirm if err.field == "confirm" else new).error = err.message
            return
        except WrongMasterPasswordError as err:
            current.error = err.message
            return
        finally:
            progress.visible = False
        for field in (current, new, confirm):
            field.value = ""
        app.notify("マスターパスワードを変更しました")

    async def export(e):
        data = app.backup.export_backup()
        # 保存先の選択画面を開くとアプリがバックグラウンド扱いになるため、その間は自動ロックしない
        with app.auto_lock.suspended():
            path = await app.file_picker.save_file(
                dialog_title="バックアップの保存先",
                file_name=BackupService.default_file_name(date.today()),
                src_bytes=data,
            )
        if path is not None:
            app.notify("バックアップを保存しました")

    async def import_(e):
        with app.auto_lock.suspended():
            files = await app.file_picker.pick_files(dialog_title="バックアップファイルを選択", with_data=True)
        if not files:
            return
        picked = files[0]
        data = picked.bytes
        if data is None and picked.path:
            data = Path(picked.path).read_bytes()
        if data is None:
            app.notify("ファイルを読み込めませんでした")
            return
        _ask_backup_password(app, data)

    appbar = ft.AppBar(
        leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="戻る", on_click=app.action(lambda e: app.show_list())),
        title=ft.Text("設定"),
    )
    content = ft.Container(
        padding=16,
        content=ft.Column(
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Text("マスターパスワードの変更", size=18, weight=ft.FontWeight.BOLD),
                current,
                new,
                confirm,
                ft.Row([ft.FilledButton(content="変更する", on_click=app.action(change)), progress]),
                ft.Divider(),
                ft.Text("バックアップ", size=18, weight=ft.FontWeight.BOLD),
                ft.Text("バックアップは暗号化されています。読み込むときは、作成したときのマスターパスワードが必要です。"),
                ft.Row(
                    wrap=True,
                    controls=[
                        ft.FilledButton(content="書き出す", icon=ft.Icons.UPLOAD_FILE, on_click=app.action(export)),
                        ft.OutlinedButton(content="読み込む", icon=ft.Icons.DOWNLOAD, on_click=app.action(import_)),
                    ],
                ),
            ],
        ),
    )
    return Screen(content, appbar)
```

- [ ] **Step 2: テストと起動確認**

Run: `Scripts/python -m pytest tests -v`
Expected: すべて PASS

Run（手動）: `Scripts/flet run src/main.py`
Expected（手動チェック）:
- 設定 → 現在のPWを間違える → 現在欄にエラー／新PW 7文字 → 新PW欄にエラー／確認不一致 → 確認欄にエラー
- 正しく変更 → 「変更しました」→ ロック → 旧PWで開けず、新PWで開けて全件見える
- 書き出す → ファイル保存 → 中身をテキストで開き、タイトル・パスワードが平文で入っていないこと
- `~/.passwordapp/vault.db` を別名に退避 → 再起動して別のマスターPWで初期設定 → 読み込む → 誤ったPWでダイアログ内エラー → 正しいPWで「追加 n件」→ もう一度読み込むと「スキップ n件」
- 確認後、退避した DB を戻す

---

### Task 11: UI 統合テスト（`flet test`）

**Files:**
- Create: `tests/ui/conftest.py`, `tests/ui/test_app_flow.py`

**Interfaces:**
- Consumes: Task 8・9 のキー（`setup_master`, `setup_confirm`, `setup_submit`, `add`, `edit_title`, `edit_password`, `edit_save`）、`main.main`

- [ ] **Step 1: テスト用の保存先を分ける** — `tests/ui/conftest.py`

```python
import os
import tempfile

# 実際のデータと混ざらないよう、アプリ起動前に一時フォルダを保存先にする
os.environ["FLET_APP_STORAGE_DATA"] = tempfile.mkdtemp(prefix="passwordapp-ui-")
```

- [ ] **Step 2: テストを書く** — `tests/ui/test_app_flow.py`

```python
import flet.testing as ftt


async def test_setup_add_and_list(flet_app: ftt.FletTestApp):
    t = flet_app.tester
    await t.pump_and_settle()

    await t.enter_text(await t.find_by_key("setup_master"), "master-pass-1")
    await t.enter_text(await t.find_by_key("setup_confirm"), "master-pass-1")
    await t.tap(await t.find_by_key("setup_submit"))
    await t.pump_and_settle()

    await t.tap(await t.find_by_key("add"))
    await t.pump_and_settle()
    await t.enter_text(await t.find_by_key("edit_title"), "GitHub")
    await t.enter_text(await t.find_by_key("edit_password"), "pw-123")
    await t.tap(await t.find_by_key("edit_save"))
    await t.pump_and_settle()

    assert (await t.find_by_text("GitHub")).count == 1
```

- [ ] **Step 3: 実行**

Run: `Scripts/python -m pip install "flet[test]>=1.0.2"` の後、`Scripts/flet test`
Expected: `test_setup_add_and_list PASSED`

`flet test` が Flutter のテスト環境を用意できない（Flutter SDK が無い等）場合は、失敗理由をそのまま記録してこのステップを「未実行」として報告し、Task 9 の手動チェックで代える。ユニットテストは以後 `Scripts/python -m pytest tests --ignore=tests/ui -v` で実行する。

---

### Task 12: Android ビルドと実機確認

**Files:**
- Modify: なし（必要ならビルド時に判明した設定のみ `pyproject.toml` の `[tool.flet]`）

- [ ] **Step 1: APK をビルド**

Run: `Scripts/flet build apk`
Expected: `build/apk/` に `.apk` ができる。初回は Flutter SDK / Android SDK のダウンロードで時間がかかる。`cryptography` の wheel が見つからないエラーが出た場合は、エラー全文を記録して止める（`pycryptodome` への切替は利用者と相談してから）。

- [ ] **Step 2: 実機で確認（利用者が実施）**

APK を端末に入れて次を確認:
- 初期設定 → 登録 → 一覧・検索・編集・削除
- ID・パスワードのコピー → 30秒後にクリップボードが空になる
- ホームボタンでアプリを裏に回す → 戻るとロック解除画面
- 5分放置 → ロック解除画面
- 書き出す（保存先選択中にロックされないこと）→ 読み込む（ファイル選択中にロックされないこと）
- マスターパスワード変更後、新しいパスワードでのみ開ける
- アプリを再起動してもデータが残っている
