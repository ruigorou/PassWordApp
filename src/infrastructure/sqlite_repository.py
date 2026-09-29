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
