import asyncio
from typing import TYPE_CHECKING

import flet as ft

from application.errors import ApplicationError
from domain.errors import ValidationError

if TYPE_CHECKING:
    from presentation.app import PasswordApp, Screen


def _password_field(label: str, key: str, autofocus: bool = False) -> ft.TextField:
    return ft.TextField(label=label, password=True, can_reveal_password=True, autofocus=autofocus, key=key)


def _layout(*controls: ft.Control) -> ft.Control:
    return ft.Container(
        padding=24,
        content=ft.Column(list(controls), spacing=16, scroll=ft.ScrollMode.AUTO),
    )


def setup_screen(app: "PasswordApp") -> "Screen":
    from presentation.app import Screen

    master = _password_field("マスターパスワード（8文字以上）", "setup_master", autofocus=True)
    confirm = _password_field("確認のためもう一度入力", "setup_confirm")
    progress = ft.ProgressRing(visible=False, width=20, height=20)

    async def create(e):
        master.error = confirm.error = None
        progress.visible = True
        app.page.update()
        try:
            await asyncio.to_thread(app.vault.setup, master.value, confirm.value)
        except ValidationError as err:
            (confirm if err.field == "confirm" else master).error = err.message
            return
        finally:
            progress.visible = False
        app.show_list()

    return Screen(
        _layout(
            ft.Text("はじめに", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("マスターパスワードを決めてください。忘れるとデータは復元できません。"),
            master,
            confirm,
            ft.Row([ft.FilledButton(content="作成", on_click=app.action(create), key="setup_submit"), progress]),
        )
    )


def unlock_screen(app: "PasswordApp") -> "Screen":
    from presentation.app import Screen

    master = _password_field("マスターパスワード", "unlock_master", autofocus=True)
    progress = ft.ProgressRing(visible=False, width=20, height=20)

    async def unlock(e):
        master.error = None
        progress.visible = True
        app.page.update()
        try:
            await asyncio.to_thread(app.vault.unlock, master.value)
        except ApplicationError as err:
            master.error = err.message
            master.value = ""
            return
        finally:
            progress.visible = False
        app.show_list()

    master.on_submit = app.action(unlock)
    return Screen(
        _layout(
            ft.Text("ロック中", size=24, weight=ft.FontWeight.BOLD),
            master,
            ft.Row([ft.FilledButton(content="開く", on_click=app.action(unlock), key="unlock_submit"), progress]),
        )
    )
