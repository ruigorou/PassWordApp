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
