from __future__ import annotations

import os
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

DEFAULT_KDF_N = 2**15
DEFAULT_KDF_R = 8
DEFAULT_KDF_P = 1
MAX_KDF_N = 2**20
# 改ざんされたバックアップで端末が固まらないための上限（既定値の 2 倍まで）
MAX_KDF_MEMORY = 2 * 128 * DEFAULT_KDF_N * DEFAULT_KDF_R  # 64MiB
MAX_KDF_COST = 2 * DEFAULT_KDF_N * DEFAULT_KDF_R * DEFAULT_KDF_P
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
            and 128 * self.n * self.r <= MAX_KDF_MEMORY
            and self.n * self.r * self.p <= MAX_KDF_COST
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
