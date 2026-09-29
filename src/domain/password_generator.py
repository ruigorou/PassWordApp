import secrets
import string
from dataclasses import dataclass

from domain.errors import ValidationError

MIN_LENGTH = 8
MAX_LENGTH = 64
DEFAULT_LENGTH = 16
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.?/"


@dataclass(frozen=True)
class GeneratorOptions:
    length: int = DEFAULT_LENGTH
    lowercase: bool = True
    uppercase: bool = True
    digits: bool = True
    symbols: bool = True


class PasswordGenerator:
    def __init__(self):
        self._rng = secrets.SystemRandom()

    def generate(self, options: GeneratorOptions = GeneratorOptions()) -> str:
        if not MIN_LENGTH <= options.length <= MAX_LENGTH:
            raise ValidationError("length", f"長さは{MIN_LENGTH}〜{MAX_LENGTH}で指定してください")
        pools = [
            pool
            for enabled, pool in (
                (options.lowercase, string.ascii_lowercase),
                (options.uppercase, string.ascii_uppercase),
                (options.digits, string.digits),
                (options.symbols, SYMBOLS),
            )
            if enabled
        ]
        if not pools:
            raise ValidationError("charset", "文字の種類を1つ以上選んでください")
        # 選んだ種類を1文字ずつ確保してから残りを埋め、最後に混ぜる
        chars = [self._rng.choice(pool) for pool in pools]
        alphabet = "".join(pools)
        chars += [self._rng.choice(alphabet) for _ in range(options.length - len(chars))]
        self._rng.shuffle(chars)
        return "".join(chars)
