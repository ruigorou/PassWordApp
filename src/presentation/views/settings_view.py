import asyncio
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import flet as ft

from application.backup_service import BackupService
from application.errors import ApplicationError, WrongMasterPasswordError
from domain.errors import ValidationError

if TYPE_CHECKING:
    from presentation.app import PasswordApp, Screen


def _password_field(label: str) -> ft.TextField:
    return ft.TextField(label=label, password=True, can_reveal_password=True)


def _ask_backup_password(app: "PasswordApp", data: bytes) -> None:
    field = ft.TextField(
        label="バックアップ作成時のマスターパスワード", password=True, can_reveal_password=True, autofocus=True
    )

    async def run(e):
        field.error = None
        try:
            result = await asyncio.to_thread(app.backup.import_backup, data, field.value)
        except ApplicationError as err:  # パスワード違い・形式不正はダイアログ内に表示
            field.error = err.message
            return
        app.page.pop_dialog()
        app.notify(f"追加 {result.added}件 / 更新 {result.updated}件 / スキップ {result.skipped}件")

    app.page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("バックアップを読み込む"),
            content=field,
            actions=[
                ft.TextButton(content="キャンセル", on_click=lambda e: app.page.pop_dialog()),
                ft.FilledButton(content="読み込む", on_click=app.action(run)),
            ],
        )
    )


def settings_screen(app: "PasswordApp") -> "Screen":
    from presentation.app import Screen

    current = _password_field("現在のマスターパスワード")
    new = _password_field("新しいマスターパスワード（8文字以上）")
    confirm = _password_field("新しいマスターパスワード（確認）")
    progress = ft.ProgressRing(visible=False, width=20, height=20)

    async def change(e):
        for field in (current, new, confirm):
            field.error = None
        progress.visible = True
        app.page.update()
        try:
            await asyncio.to_thread(app.vault.change_master_password, current.value, new.value, confirm.value)
        except ValidationError as err:
            (confirm if err.field == "confirm" else new).error = err.message
            return
        except WrongMasterPasswordError as err:
            current.error = err.message
            return
        finally:
            progress.visible = False
        for field in (current, new, confirm):
            field.value = ""
        app.notify("マスターパスワードを変更しました")

    async def export(e):
        data = app.backup.export_backup()
        # 保存先の選択画面を開くとアプリがバックグラウンド扱いになるため、その間は自動ロックしない
        with app.auto_lock.suspended():
            path = await app.file_picker.save_file(
                dialog_title="バックアップの保存先",
                file_name=BackupService.default_file_name(date.today()),
                src_bytes=data,
            )
        if path is not None:
            app.notify("バックアップを保存しました")

    async def import_(e):
        with app.auto_lock.suspended():
            files = await app.file_picker.pick_files(dialog_title="バックアップファイルを選択", with_data=True)
        if not files:
            return
        picked = files[0]
        data = picked.bytes
        if data is None and picked.path:
            data = Path(picked.path).read_bytes()
        if data is None:
            app.notify("ファイルを読み込めませんでした")
            return
        _ask_backup_password(app, data)

    appbar = ft.AppBar(
        leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="戻る", on_click=app.action(lambda e: app.show_list())),
        title=ft.Text("設定"),
    )
    content = ft.Container(
        padding=16,
        content=ft.Column(
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Text("マスターパスワードの変更", size=18, weight=ft.FontWeight.BOLD),
                current,
                new,
                confirm,
                ft.Row([ft.FilledButton(content="変更する", on_click=app.action(change)), progress]),
                ft.Divider(),
                ft.Text("バックアップ", size=18, weight=ft.FontWeight.BOLD),
                ft.Text("バックアップは暗号化されています。読み込むときは、作成したときのマスターパスワードが必要です。"),
                ft.Row(
                    wrap=True,
                    controls=[
                        ft.FilledButton(content="書き出す", icon=ft.Icons.UPLOAD_FILE, on_click=app.action(export)),
                        ft.OutlinedButton(content="読み込む", icon=ft.Icons.DOWNLOAD, on_click=app.action(import_)),
                    ],
                ),
            ],
        ),
    )
    return Screen(content, appbar)
