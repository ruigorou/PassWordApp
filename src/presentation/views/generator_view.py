from typing import TYPE_CHECKING, Callable

import flet as ft

from domain.errors import ValidationError
from domain.password_generator import DEFAULT_LENGTH, MAX_LENGTH, MIN_LENGTH, GeneratorOptions

if TYPE_CHECKING:
    from presentation.app import PasswordApp, Screen

KINDS = (
    ("lowercase", "小文字 a-z"),
    ("uppercase", "大文字 A-Z"),
    ("digits", "数字 0-9"),
    ("symbols", "記号 !@#…"),
)


def generator_panel(app: "PasswordApp") -> tuple[ft.Control, Callable[[], str]]:
    state = {"value": ""}
    result = ft.Text(size=20, selectable=True, font_family="monospace")
    error = ft.Text(color=ft.Colors.ERROR, visible=False)
    length_label = ft.Text()
    length = ft.Slider(min=MIN_LENGTH, max=MAX_LENGTH, divisions=MAX_LENGTH - MIN_LENGTH, value=DEFAULT_LENGTH)
    checks = {name: ft.Checkbox(label=label, value=True) for name, label in KINDS}

    def regenerate():
        options = GeneratorOptions(
            length=int(length.value), **{name: bool(box.value) for name, box in checks.items()}
        )
        length_label.value = f"長さ: {options.length}"
        try:
            state["value"] = app.generator.generate(options)
            error.visible = False
        except ValidationError as err:
            state["value"] = ""
            error.value = err.message
            error.visible = True
        result.value = state["value"]

    handler = app.action(lambda e: regenerate())
    length.on_change = handler
    for box in checks.values():
        box.on_change = handler
    regenerate()

    panel = ft.Column(
        tight=True,
        controls=[
            result,
            error,
            length_label,
            length,
            *checks.values(),
            ft.TextButton(content="作り直す", icon=ft.Icons.REFRESH, on_click=handler),
        ],
    )
    return panel, lambda: state["value"]


def generator_screen(app: "PasswordApp") -> "Screen":
    from presentation.app import Screen

    panel, current = generator_panel(app)

    async def copy(e):
        if current():
            await app.copy(current(), "パスワード")

    appbar = ft.AppBar(
        leading=ft.IconButton(icon=ft.Icons.ARROW_BACK, tooltip="戻る", on_click=app.action(lambda e: app.show_list())),
        title=ft.Text("パスワード生成"),
    )
    content = ft.Container(
        padding=16,
        content=ft.Column(
            scroll=ft.ScrollMode.AUTO,
            controls=[panel, ft.FilledButton(content="コピー", icon=ft.Icons.CONTENT_COPY, on_click=app.action(copy))],
        ),
    )
    return Screen(content, appbar)


def open_generator_dialog(app: "PasswordApp", on_use: Callable[[str], None]) -> None:
    panel, current = generator_panel(app)

    def use(e):
        value = current()
        app.page.pop_dialog()
        if value:
            on_use(value)

    dialog = ft.AlertDialog(
        title=ft.Text("パスワード生成"),
        content=panel,
        actions=[
            ft.TextButton(content="キャンセル", on_click=lambda e: app.page.pop_dialog()),
            ft.FilledButton(content="使う", on_click=app.action(use)),
        ],
    )
    app.page.show_dialog(dialog)
