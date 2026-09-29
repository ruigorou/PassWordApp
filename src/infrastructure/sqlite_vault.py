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
