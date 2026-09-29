import string

import pytest

from domain.errors import ValidationError
from domain.password_generator import SYMBOLS, GeneratorOptions, PasswordGenerator

KINDS = (string.ascii_lowercase, string.ascii_uppercase, string.digits, SYMBOLS)


def test_default_is_16_chars_with_every_kind():
    for _ in range(50):
        pw = PasswordGenerator().generate()
        assert len(pw) == 16
        for kind in KINDS:
            assert any(ch in kind for ch in pw)


@pytest.mark.parametrize("length", [8, 64])
def test_boundary_lengths(length):
    assert len(PasswordGenerator().generate(GeneratorOptions(length=length))) == length


@pytest.mark.parametrize("length", [7, 65])
def test_out_of_range_length(length):
    with pytest.raises(ValidationError) as e:
        PasswordGenerator().generate(GeneratorOptions(length=length))
    assert e.value.field == "length"


def test_only_digits():
    options = GeneratorOptions(lowercase=False, uppercase=False, symbols=False)
    assert PasswordGenerator().generate(options).isdigit()


def test_no_kind_selected():
    options = GeneratorOptions(lowercase=False, uppercase=False, digits=False, symbols=False)
    with pytest.raises(ValidationError) as e:
        PasswordGenerator().generate(options)
    assert e.value.field == "charset"


def test_min_length_still_contains_every_kind():
    for _ in range(200):
        pw = PasswordGenerator().generate(GeneratorOptions(length=8))
        for kind in KINDS:
            assert any(ch in kind for ch in pw)


def test_outputs_differ():
    generator = PasswordGenerator()
    assert len({generator.generate() for _ in range(20)}) == 20
