import asyncio

from presentation.session_guard import AutoLock, ClipboardCleaner


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeClipboard:
    def __init__(self):
        self.value = None

    async def set(self, value):
        self.value = value

    async def get(self):
        return self.value


def test_idle_expires_after_timeout_and_touch_resets():
    clock = FakeClock()
    lock = AutoLock(idle_timeout=300, clock=clock)
    clock.now = 299
    assert not lock.idle_expired()
    lock.touch()
    clock.now = 598
    assert not lock.idle_expired()
    clock.now = 599
    assert lock.idle_expired()


def test_suspended_blocks_background_lock_and_idle():
    clock = FakeClock()
    lock = AutoLock(idle_timeout=300, clock=clock, max_suspend=10_000)
    assert lock.should_lock_on_background()
    with lock.suspended():
        clock.now = 1000
        assert not lock.should_lock_on_background()
        assert not lock.idle_expired()
    # ファイル選択から戻った直後は無操作時間をリセットする
    assert lock.should_lock_on_background()
    assert not lock.idle_expired()


async def test_clipboard_is_cleared_after_delay():
    clipboard = FakeClipboard()

    async def no_wait(_):
        pass

    cleaner = ClipboardCleaner(clipboard, sleep=no_wait)
    await cleaner.copy("secret")
    assert clipboard.value == "secret"
    await cleaner.wait()
    assert clipboard.value == ""


async def test_clipboard_is_kept_if_user_copied_something_else():
    clipboard = FakeClipboard()
    gate = asyncio.Event()

    async def wait_gate(_):
        await gate.wait()

    cleaner = ClipboardCleaner(clipboard, sleep=wait_gate)
    await cleaner.copy("secret")
    clipboard.value = "other text"
    gate.set()
    await cleaner.wait()
    assert clipboard.value == "other text"


async def test_second_copy_cancels_first_timer():
    clipboard = FakeClipboard()
    gate = asyncio.Event()

    async def wait_gate(_):
        await gate.wait()

    cleaner = ClipboardCleaner(clipboard, sleep=wait_gate)
    await cleaner.copy("first")
    first = cleaner._task
    await cleaner.copy("second")
    await asyncio.sleep(0)
    assert first.cancelled()
    gate.set()
    await cleaner.wait()
    assert clipboard.value == ""


def test_suspension_expires_if_picker_never_returns():
    clock = FakeClock()
    lock = AutoLock(idle_timeout=300, clock=clock, max_suspend=300)
    with lock.suspended():
        clock.now = 299
        assert not lock.should_lock_on_background()
        clock.now = 301
        assert lock.should_lock_on_background()
        assert lock.idle_expired()
