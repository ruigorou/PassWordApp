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


@pytest.mark.parametrize(
    "n, r, p",
    [
        (2**20, 16, 4),  # 約 2GiB のメモリを要求する改ざん値
        (2**20, 8, 1),   # 128MiB
        (2**15, 8, 4),   # 計算量が既定の4倍
    ],
)
def test_expensive_kdf_params_are_rejected(n, r, p):
    with pytest.raises(ValueError):
        KdfParams(salt=os.urandom(16), n=n, r=r, p=p)


def test_default_kdf_params_are_accepted():
    KdfParams.generate()
