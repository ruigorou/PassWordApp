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
