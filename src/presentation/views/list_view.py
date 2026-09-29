from typing import TYPE_CHECKING

import flet as ft

from domain.credential import Credential

if TYPE_CHECKING:
    from presentation.app import PasswordApp, Screen


def _tile(app: "PasswordApp", credential: Credential) -> ft.ListTile:
    async def copy_id(e):
        await app.copy(credential.login_id, "ID")

    async def copy_password(e):
        await app.copy(credential.password.value, "パスワード")

    return ft.ListTile(
        title=credential.title.value,
        subtitle=credential.login_id or None,
        on_click=app.action(lambda e: app.show_edit(credential)),
        trailing=ft.Row(
            tight=True,
            controls=[
                ft.IconButton(
                    icon=ft.Icons.PERSON,
                    tooltip="IDをコピー",
                    disabled=not credential.login_id,
                    on_click=app.action(copy_id),
                ),
                ft.IconButton(icon=ft.Icons.KEY, tooltip="パスワードをコピー", on_click=app.action(copy_password)),
            ],
        ),
    )


def list_screen(app: "PasswordApp") -> "Screen":
    from presentation.app import Screen

    search = ft.TextField(hint_text="検索（タイトル・ID・URL・メモ）", prefix_icon=ft.Icons.SEARCH, key="search")
    notice = ft.Text(color=ft.Colors.ERROR, visible=False)
    items = ft.ListView(expand=True)

    def refresh():
        result = app.credentials.search(search.value)
        notice.value = f"読めないデータが {result.unreadable} 件あります"
        notice.visible = result.unreadable > 0
        if result.items:
            items.controls = [_tile(app, c) for c in result.items]
        else:
            empty = "見つかりません" if search.value.strip() else "まだ登録がありません。＋ボタンで追加してください"
            items.controls = [ft.Container(ft.Text(empty), padding=16)]

    search.on_change = app.action(lambda e: refresh())
    refresh()

    appbar = ft.AppBar(
        title=ft.Text("パスワード"),
        actions=[
            ft.IconButton(icon=ft.Icons.PASSWORD, tooltip="パスワード生成", on_click=app.action(lambda e: app.show_generator())),
            ft.IconButton(icon=ft.Icons.SETTINGS, tooltip="設定", on_click=app.action(lambda e: app.show_settings())),
            ft.IconButton(icon=ft.Icons.LOCK, tooltip="ロック", on_click=app.action(lambda e: app.lock())),
        ],
    )
    fab = ft.FloatingActionButton(icon=ft.Icons.ADD, tooltip="追加", key="add", on_click=app.action(lambda e: app.show_edit()))
    content = ft.Column(
        expand=True,
        controls=[ft.Container(search, padding=ft.Padding.symmetric(horizontal=16, vertical=8)), notice, items],
    )
    return Screen(content, appbar, fab)
