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
