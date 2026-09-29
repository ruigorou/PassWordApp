from typing import TYPE_CHECKING

import flet as ft

from application.credential_service import CredentialInput
from domain.credential import Credential
from domain.errors import ValidationError
from presentation.views.generator_view import open_generator_dialog

if TYPE_CHECKING:
    from presentation.app import PasswordApp, Screen


def edit_screen(app: "PasswordApp", credential: Credential | None) -> "Screen":
    from presentation.app import Screen

    is_new = credential is None
    title = ft.TextField(label="タイトル *", key="edit_title")
    login_id = ft.TextField(label="ID", key="edit_login_id")
    password = ft.TextField(label="パスワード *", password=True, can_reveal_password=True, expand=True, key="edit_password")
    url = ft.TextField(label="URL", hint_text="https://", keyboard_type=ft.KeyboardType.URL, key="edit_url")
    memo = ft.TextField(label="メモ", multiline=True, min_lines=3, max_lines=8, key="edit_memo")
    fields = {"title": title, "login_id": login_id, "password": password, "url": url, "memo": memo}

    if credential is not None:
        title.value = credential.title.value
        login_id.value = credential.login_id
        password.value = credential.password.value
        url.value = credential.url.value if credential.url else ""
        memo.value = credential.memo

    def use_generated(value: str):
        password.value = value
        app.page.update()

    def save(e):
        for field in fields.values():
            field.error = None
        data = CredentialInput(title.value, login_id.value, password.value, url.value, memo.value)
        try:
            if is_new:
                app.credentials.add(data)
            else:
                app.credentials.edit(credential.id.value, data)
        except ValidationError as err:
            fields[err.field].error = err.message
            return
        app.notify("保存しました")
        app.show_list()

    def delete():
        app.credentials.delete(credential.id.value)
        app.notify("削除しました")
        app.show_list()

    def ask_delete(e):
        app.confirm("削除しますか？", f"「{credential.title.value}」を削除します。元に戻せません。", delete)

    actions = [] if is_new else [ft.IconButton(icon=ft.Icons.DELETE, tooltip="削除", on_click=app.action(ask_delete))]
    appbar = ft.AppBar(
        leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="戻る", on_click=app.action(lambda e: app.show_list())),
        title=ft.Text("新規登録" if is_new else "編集"),
        actions=actions,
    )
    generate = ft.IconButton(
        icon=ft.Icons.AUTO_AWESOME,
        tooltip="パスワードを生成",
        on_click=app.action(lambda e: open_generator_dialog(app, use_generated)),
    )
    content = ft.Container(
        padding=16,
        content=ft.Column(
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                title,
                login_id,
                ft.Row([password, generate]),
                url,
                memo,
                ft.FilledButton(content="保存", icon=ft.Icons.SAVE, on_click=app.action(save), key="edit_save"),
            ],
        ),
    )
    return Screen(content, appbar)
