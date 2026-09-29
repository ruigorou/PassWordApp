import asyncio
import time
from contextlib import contextmanager
from typing import Awaitable, Callable, Protocol

IDLE_TIMEOUT_SECONDS = 300.0
CLIPBOARD_CLEAR_SECONDS = 30.0
MAX_SUSPEND_SECONDS = 300.0


class AutoLock:
    """無操作時間と、外部画面（ファイル選択など）を開いている状態を管理する。"""

    def __init__(
        self,
        idle_timeout: float = IDLE_TIMEOUT_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        max_suspend: float = MAX_SUSPEND_SECONDS,
    ):
        self._idle_timeout = idle_timeout
        self._clock = clock
        self._max_suspend = max_suspend
        self._last_activity = clock()
        self._suspended = 0
        self._suspended_since = 0.0

    def touch(self) -> None:
        self._last_activity = self._clock()

    @contextmanager
    def suspended(self):
        if self._suspended == 0:
            self._suspended_since = self._clock()
        self._suspended += 1
        try:
            yield
        finally:
            self._suspended -= 1
            self.touch()

    def _is_suspended(self) -> bool:
        # ファイル選択から戻ってこない場合に備え、一時停止には期限を設ける
        return self._suspended > 0 and self._clock() - self._suspended_since < self._max_suspend

    def should_lock_on_background(self) -> bool:
        return not self._is_suspended()

    def idle_expired(self) -> bool:
        return not self._is_suspended() and self._clock() - self._last_activity >= self._idle_timeout


class ClipboardPort(Protocol):
    async def set(self, value: str) -> None: ...

    async def get(self) -> str | None: ...


class ClipboardCleaner:
    """コピーした値を一定時間後に消す。別の内容に変わっていたら触らない。"""

    def __init__(
        self,
        clipboard: ClipboardPort,
        delay: float = CLIPBOARD_CLEAR_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._clipboard = clipboard
        self._delay = delay
        self._sleep = sleep
        self._task: asyncio.Task | None = None

    async def copy(self, value: str) -> None:
        await self._clipboard.set(value)
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = asyncio.create_task(self._clear_later(value))

    async def _clear_later(self, value: str) -> None:
        await self._sleep(self._delay)
        try:
            if await self._clipboard.get() == value:
                await self._clipboard.set("")
        except Exception:
            pass  # クリップボードが使えない状態（アプリ終了中など）では何もしない

    async def wait(self) -> None:
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
