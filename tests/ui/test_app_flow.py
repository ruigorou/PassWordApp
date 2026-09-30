import flet.testing as ftt


async def test_setup_add_and_list(flet_app: ftt.FletTestApp):
    t = flet_app.tester
    await t.pump_and_settle()

    await t.enter_text(await t.find_by_key("setup_master"), "master-pass-1")
    await t.enter_text(await t.find_by_key("setup_confirm"), "master-pass-1")
    await t.tap(await t.find_by_key("setup_submit"))
    await t.pump_and_settle()

    await t.tap(await t.find_by_key("add"))
    await t.pump_and_settle()
    await t.enter_text(await t.find_by_key("edit_title"), "GitHub")
    await t.enter_text(await t.find_by_key("edit_password"), "pw-123")
    await t.tap(await t.find_by_key("edit_save"))
    await t.pump_and_settle()

    assert (await t.find_by_text("GitHub")).count == 1
    assert (await t.find_by_text("1件")).count == 1
