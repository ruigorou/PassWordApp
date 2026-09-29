import threading
import time
from contextlib import contextmanager
from typing import Callable

from application.errors import (
    TooManyAttemptsError,
    VaultBusyError,
    VaultLockedError,
    WrongMasterPasswordError,
)
from application.ports import VaultStore
from domain.errors import ValidationError
from domain.repository import CredentialRepository

MIN_MASTER_LENGTH = 8
MAX_FAILURES = 5
LOCKOUT_SECONDS = 30.0


def _validate_new_master(master: str, confirm: str) -> None:
    if len(master) < MIN_MASTER_LENGTH:
        raise ValidationError("master", f"マスターパスワードは{MIN_MASTER_LENGTH}文字以上にしてください")
    if master != confirm:
        raise ValidationError("confirm", "確認用のパスワードが一致しません")


class VaultService:
    def __init__(self, store: VaultStore, clock: Callable[[], float] = time.monotonic):
        self._store = store
        self._clock = clock
        self._repository: CredentialRepository | None = None
        self._failures = 0
        self._locked_until = 0.0
        self._busy = threading.Lock()
        self._busy_owner: int | None = None
        self._lock_epoch = 0  # lock() のたびに増える。処理中にロックされたかの判定に使う

    @contextmanager
    def exclusive(self):
        """時間のかかる処理（鍵導出・一括書き込み）の間、他の操作を受け付けない。"""
        if not self._busy.acquire(blocking=False):
            raise VaultBusyError()
        self._busy_owner = threading.get_ident()
        try:
            yield
        finally:
            self._busy_owner = None
            self._busy.release()

    def _accept(self, repository: CredentialRepository, epoch: int) -> None:
        # 処理中にロックされていたら結果を捨てる（裏に回った間に解除状態へ戻さない）
        if epoch != self._lock_epoch:
            raise VaultLockedError()
        self._repository = repository

    def is_initialized(self) -> bool:
        return self._store.is_initialized()

    @property
    def is_unlocked(self) -> bool:
        return self._repository is not None

    def setup(self, master: str, confirm: str) -> None:
        _validate_new_master(master, confirm)
        with self.exclusive():
            epoch = self._lock_epoch
            self._accept(self._store.initialize(master), epoch)

    def unlock(self, master: str) -> None:
        now = self._clock()
        if now < self._locked_until:
            raise TooManyAttemptsError(self._locked_until - now)
        with self.exclusive():
            epoch = self._lock_epoch
            try:
                repository = self._store.open(master)
            except WrongMasterPasswordError:
                self._failures += 1
                if self._failures >= MAX_FAILURES:
                    self._failures = 0
                    self._locked_until = now + LOCKOUT_SECONDS
                raise
            self._failures = 0
            self._accept(repository, epoch)

    def lock(self) -> None:
        # 鍵を持つリポジトリへの参照を捨てる（Python ではメモリの確実な消去はできない）
        self._lock_epoch += 1
        self._repository = None

    def repository(self) -> CredentialRepository:
        if self._busy.locked() and self._busy_owner != threading.get_ident():
            raise VaultBusyError()
        if self._repository is None:
            raise VaultLockedError()
        return self._repository

    def change_master_password(self, current: str, new: str, confirm: str) -> None:
        _validate_new_master(new, confirm)
        with self.exclusive():
            self.repository()
            epoch = self._lock_epoch
            self._accept(self._store.change_master_password(current, new), epoch)
