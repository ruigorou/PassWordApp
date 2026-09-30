from dataclasses import dataclass

from application.vault_service import VaultService
from domain.credential import Credential, CredentialId
from domain.errors import CredentialNotFoundError
@dataclass(frozen=True)
class SearchResult:
    items: list[Credential]
    unreadable: int  # 復号できなかった件数
    total: int  # 検索条件に関係なく読めた登録件数


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

    def search(self, query: str = "") -> SearchResult:
        result = self._vault.repository().list_all()
        items = sorted(
            (c for c in result.items if c.matches(query)),
            key=lambda c: c.title.value.casefold(),
        )
        return SearchResult(items, result.unreadable, len(result.items))

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
