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
