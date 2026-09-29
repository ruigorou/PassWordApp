import asyncio
import inspect
import sqlite3
from dataclasses import dataclass

import flet as ft

from application.backup_service import BackupService
from application.credential_service import CredentialService
from application.errors import ApplicationError
from application.vault_service import VaultService
from domain.credential import Credential
from domain.errors import DomainError
from domain.password_generator import PasswordGenerator
from presentation.session_guard import CLIPBOARD_CLEAR_SECONDS, AutoLock, ClipboardCleaner

IDLE_CHECK_INTERVAL_SECONDS = 10
BACKGROUND_STATES = (ft.AppLifecycleState.HIDE, ft.AppLifecycleState.PAUSE)


@dataclass
class Screen:
    content: ft.Control
    appbar: ft.AppBar | None = None
    fab: ft.FloatingActionButton | None = None


class PasswordApp:
    def __init__(
        self,
        page: ft.Page,
        vault: VaultService,
        credentials: CredentialService,
        backup: BackupService,
        generator: PasswordGenerator,
    ):
        self.page = page
        self.vault = vault
        self.credentials = credentials
        self.backup = backup
        self.generator = generator
        self.auto_lock = AutoLock()
        # Flet のサービスは強参照がないと解除されるので、このオブジェクトで保持する
        self.clipboard = ft.Clipboard()
        self.file_picker = ft.FilePicker()
        self._clipboard_cleaner = ClipboardCleaner(self.clipboard)

    def start(self) -> None:
        self.page.title = "パスワード管理"
        self.page.on_app_lifecycle_state_change = self._on_lifecycle
        self.page.run_task(self._watch_idle)
        self.show_start()

    # --- 画面切替 -------------------------------------------------------------

    def show(self, screen: Screen) -> None:
        self.auto_lock.touch()
        self.page.appbar = screen.appbar
        self.page.floating_action_button = screen.fab
        self.page.controls.clear()
        self.page.controls.append(ft.SafeArea(expand=True, content=screen.content))
        self.page.update()

    def show_start(self) -> None:
        from presentation.views.lock_views import setup_screen, unlock_screen

        self.show(unlock_screen(self) if self.vault.is_initialized() else setup_screen(self))

    def show_unlock(self) -> None:
        from presentation.views.lock_views import unlock_screen

        self.show(unlock_screen(self))

    def show_list(self) -> None:
        from presentation.views.list_view import list_screen

        self.show(list_screen(self))

    def show_edit(self, credential: Credential | None = None) -> None:
        from presentation.views.edit_view import edit_screen

        self.show(edit_screen(self, credential))

    def show_generator(self) -> None:
        from presentation.views.generator_view import generator_screen

        self.show(generator_screen(self))

    def show_settings(self) -> None:
        from presentation.views.settings_view import settings_screen

        self.show(settings_screen(self))

    # --- ロック ---------------------------------------------------------------

    def lock(self) -> None:
        # 解除処理の途中でも呼ぶ（VaultService が処理中の結果を捨てる）
        self.vault.lock()
        self.page.pop_dialog()
        self.show_start()

    async def _on_lifecycle(self, e: ft.AppLifecycleStateChangeEvent) -> None:
        if e.state in BACKGROUND_STATES and self.auto_lock.should_lock_on_background():
            self.lock()

    async def _watch_idle(self) -> None:
        while True:
            await asyncio.sleep(IDLE_CHECK_INTERVAL_SECONDS)
            if self.vault.is_unlocked and self.auto_lock.idle_expired():
                self.lock()

    # --- 共通の操作 -----------------------------------------------------------

    def action(self, handler):
        """イベントハンドラを包む: 操作時刻の記録と、想定内エラーの表示。"""

        async def wrapped(e):
            self.auto_lock.touch()
            try:
                result = handler(e)
                if inspect.isawaitable(result):
                    await result
            except (DomainError, ApplicationError) as err:
                self.notify(err.message)
            except sqlite3.Error:
                self.notify("データの保存・読み込みに失敗しました")

        return wrapped

    def notify(self, message: str) -> None:
        self.page.show_dialog(ft.SnackBar(ft.Text(message)))

    async def copy(self, value: str, label: str) -> None:
        await self._clipboard_cleaner.copy(value)
        self.notify(f"{label}をコピーしました（{int(CLIPBOARD_CLEAR_SECONDS)}秒後に消去）")

    def confirm(self, title: str, message: str, on_yes) -> None:
        def yes(e):
            self.page.pop_dialog()
            on_yes()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton(content="キャンセル", on_click=lambda e: self.page.pop_dialog()),
                ft.FilledButton(content="削除", on_click=self.action(yes)),
            ],
        )
        self.page.show_dialog(dialog)
