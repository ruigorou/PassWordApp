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
        with self._vault.exclusive():
            return self._import(data, backup_master)

    def _import(self, data: bytes, backup_master: str) -> ImportResult:
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
