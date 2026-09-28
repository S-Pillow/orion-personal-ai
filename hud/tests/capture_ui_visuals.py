from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from probe_ui_convergence import UIConvergenceFixture


OUT = Path("ui-visual-artifacts")
OUT.mkdir(exist_ok=True)


def rect(page, selector: str) -> dict[str, float]:
    value = page.locator(selector).bounding_box()
    if value is None:
        raise AssertionError(f"missing rectangle for {selector}")
    return value


def overlap(a: dict[str, float], b: dict[str, float]) -> bool:
    return not (
        a["x"] + a["width"] <= b["x"]
        or b["x"] + b["width"] <= a["x"]
        or a["y"] + a["height"] <= b["y"]
        or b["y"] + b["height"] <= a["y"]
    )


def wait_review(page) -> None:
    page.wait_for_function(
        "() => document.querySelector('#sessionSelect')?.value === 'session_1'"
    )
    page.wait_for_function(
        "() => document.querySelectorAll('.message').length >= 4"
    )


def review_capture(browser, fixture, width: int, height: int, name: str) -> dict:
    page = browser.new_page(viewport={"width": width, "height": height})
    page.goto(fixture.review_url, wait_until="networkidle")
    wait_review(page)

    header = rect(page, ".topbar")
    left = rect(page, ".context-sidebar")
    right = rect(page, ".activity-sidebar")
    conversation = rect(page, ".conversation-workspace")
    composer = rect(page, ".composer")
    core = rect(page, ".core-visual")
    state = rect(page, "#coreState")

    assert 50 <= header["height"] <= 64
    assert 205 <= left["width"] <= 270
    assert 300 <= right["width"] <= 420
    assert 760 <= conversation["width"] <= 960
    assert conversation["x"] + conversation["width"] <= right["x"] + 2
    assert composer["y"] >= conversation["y"] + conversation["height"]
    assert core["y"] >= header["height"] - 2
    assert state["y"] + state["height"] <= conversation["y"] + 1
    assert not overlap(state, conversation)

    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    report = {
        "viewport": [width, height],
        "header": header,
        "left": left,
        "right": right,
        "conversation": conversation,
        "composer": composer,
        "core": core,
        "core_state": state,
    }
    page.close()
    return report


def keyboard_approval_check(page) -> None:
    buttons = page.locator("#approvalActions button")
    assert buttons.count() == 4
    buttons.nth(0).focus()
    assert page.evaluate("document.activeElement === document.querySelectorAll('#approvalActions button')[0]")
    for index in range(1, 4):
        page.keyboard.press("Tab")
        assert page.evaluate(
            f"document.activeElement === document.querySelectorAll('#approvalActions button')[{index}]"
        )


def mobile_review_capture(browser, fixture) -> dict:
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(fixture.review_url, wait_until="networkidle")
    wait_review(page)
    state = rect(page, "#coreState")
    conversation = rect(page, ".conversation-workspace")
    composer = rect(page, ".composer")
    assert state["y"] + state["height"] <= conversation["y"] + 1
    assert not overlap(state, conversation)
    assert composer["width"] <= 374
    assert composer["y"] >= 0
    assert composer["y"] + composer["height"] <= 844.5
    page.screenshot(path=str(OUT / "mobile-review-390x844.png"), full_page=False)
    page.close()
    return {
        "core_state": state,
        "conversation": conversation,
        "composer": composer,
    }


def pending_approval_capture(browser, fixture) -> dict:
    page = browser.new_page(viewport={"width": 1672, "height": 941})
    page.goto(fixture.approval_url, wait_until="domcontentloaded")
    page.wait_for_function(
        "() => !document.querySelector('#approvalPanel')?.classList.contains('hidden')"
    )
    approval = rect(page, "#approvalPanel")
    right = rect(page, ".activity-sidebar")
    conversation = rect(page, ".conversation-workspace")
    buttons = page.locator("#approvalActions button")
    assert buttons.count() == 4
    keyboard_approval_check(page)
    for index in range(buttons.count()):
        box = buttons.nth(index).bounding_box()
        assert box is not None
        assert box["x"] >= approval["x"] - 1
        assert box["x"] + box["width"] <= approval["x"] + approval["width"] + 1
    assert conversation["x"] + conversation["width"] <= right["x"] + 2
    page.screenshot(path=str(OUT / "desktop-approval-1672x941.png"), full_page=True)
    page.get_by_role("button", name="DENY").click()
    page.wait_for_function(
        "() => document.querySelector('#approvalPanel')?.classList.contains('hidden')"
    )
    page.close()
    return {"approval": approval, "right": right, "conversation": conversation}


def approval_capture(browser, fixture) -> dict:
    page = browser.new_page(viewport={"width": 1672, "height": 941})
    page.goto(fixture.summon_approval_url, wait_until="domcontentloaded")
    page.wait_for_function(
        "() => !document.querySelector('#approvalPanel')?.classList.contains('hidden')"
    )
    approval = rect(page, "#approvalPanel")
    right = rect(page, ".activity-sidebar")
    conversation = rect(page, ".conversation-workspace")
    buttons = page.locator("#approvalActions button")
    assert buttons.count() == 4
    keyboard_approval_check(page)
    for index in range(buttons.count()):
        box = buttons.nth(index).bounding_box()
        assert box is not None
        assert box["x"] >= approval["x"] - 1
        assert box["x"] + box["width"] <= approval["x"] + approval["width"] + 1
    assert conversation["x"] + conversation["width"] <= right["x"] + 2
    page.screenshot(path=str(OUT / "desktop-summon-approval.png"), full_page=True)
    page.get_by_role("button", name="DENY").click()
    page.wait_for_function(
        "() => document.querySelector('#approvalPanel')?.classList.contains('hidden')"
    )
    page.close()
    return {"approval": approval, "right": right, "conversation": conversation}


def offline_capture(browser, fixture) -> dict:
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(fixture.offline_url, wait_until="networkidle")
    page.wait_for_function(
        "() => document.querySelector('#coreStage')?.dataset.coreState === 'OFFLINE'"
    )
    status = page.locator("#hermesStatus")
    core = page.locator(".core-visual")
    assert "offline" in (status.get_attribute("class") or "")
    status_color = status.evaluate("(el) => getComputedStyle(el).color")
    core_opacity = core.evaluate("(el) => getComputedStyle(el).opacity")
    assert status_color == "rgb(214, 124, 114)"
    assert abs(float(core_opacity) - 0.52) < 0.01
    page.screenshot(path=str(OUT / "desktop-offline.png"), full_page=True)
    page.close()
    return {"status_color": status_color, "core_opacity": core_opacity}


def mobile_approval_capture(browser, fixture) -> dict:
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(fixture.summon_approval_url, wait_until="domcontentloaded")
    page.wait_for_function(
        "() => !document.querySelector('#approvalPanel')?.classList.contains('hidden')"
    )
    panel = page.locator("#approvalPanel")
    panel.scroll_into_view_if_needed()
    approval = rect(page, "#approvalPanel")
    right = rect(page, ".activity-sidebar")
    assert right["width"] <= 390.5
    assert approval["width"] <= 358
    buttons = page.locator("#approvalActions button")
    assert buttons.count() == 4
    keyboard_approval_check(page)
    for index in range(buttons.count()):
        box = buttons.nth(index).bounding_box()
        assert box is not None
        assert box["x"] >= -1
        assert box["x"] + box["width"] <= 391
    page.screenshot(path=str(OUT / "mobile-approval-390x844.png"), full_page=False)
    page.get_by_role("button", name="DENY").click()
    page.wait_for_function(
        "() => document.querySelector('#approvalPanel')?.classList.contains('hidden')"
    )
    page.close()
    return {"approval": approval, "right": right}


def motion_preference_check(browser, fixture) -> dict:
    full = browser.new_page(viewport={"width": 1440, "height": 900})
    full.emulate_media(reduced_motion="no-preference")
    full.goto(fixture.motion_url, wait_until="networkidle")
    full.wait_for_function(
        "() => document.querySelector('#coreStage')?.dataset.coreState === 'THINKING'"
    )
    full_animation = full.locator(".core-halo-outer").evaluate(
        "(el) => getComputedStyle(el).animationName"
    )
    full_motion = full.locator("#coreStage").get_attribute("data-motion")
    assert full_animation == "core-pulse"
    assert full_motion == "full"
    full.close()

    reduced = browser.new_page(viewport={"width": 1440, "height": 900})
    reduced.emulate_media(reduced_motion="reduce")
    reduced.goto(fixture.motion_url, wait_until="networkidle")
    reduced.wait_for_function(
        "() => document.querySelector('#coreStage')?.dataset.coreState === 'THINKING'"
    )
    reduced_animation = reduced.locator(".core-halo-outer").evaluate(
        "(el) => getComputedStyle(el).animationName"
    )
    reduced_motion = reduced.locator("#coreStage").get_attribute("data-motion")
    reduced.close()
    assert reduced_animation == "none"
    assert reduced_motion == "reduced"
    return {
        "full_animation": full_animation,
        "full_motion": full_motion,
        "reduced_animation": reduced_animation,
        "reduced_motion": reduced_motion,
    }


def mobile_keyboard_capture(browser, fixture) -> dict:
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(fixture.review_url, wait_until="networkidle")
    wait_review(page)
    page.locator("#messageInput").focus()
    page.set_viewport_size({"width": 390, "height": 520})
    page.wait_for_timeout(150)
    composer = rect(page, ".composer")
    assert composer["y"] >= 0
    assert composer["y"] + composer["height"] <= 520.5
    page.screenshot(
        path=str(OUT / "mobile-keyboard-simulated-390x520.png"),
        full_page=False,
    )
    page.close()
    return {"composer": composer, "viewport": [390, 520]}


def main() -> None:
    fixture = UIConvergenceFixture()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            report = {
                "desktop_1672x941": review_capture(
                    browser, fixture, 1672, 941, "desktop-review-1672x941"
                ),
                "desktop_1440x900": review_capture(
                    browser, fixture, 1440, 900, "desktop-review-1440x900"
                ),
                "desktop_1366x768": review_capture(
                    browser, fixture, 1366, 768, "desktop-review-1366x768"
                ),
                "mobile_review": mobile_review_capture(browser, fixture),
                "pending_approval": pending_approval_capture(browser, fixture),
                "summon_approval": approval_capture(browser, fixture),
                "offline": offline_capture(browser, fixture),
                "mobile_approval": mobile_approval_capture(browser, fixture),
                "mobile_keyboard": mobile_keyboard_capture(browser, fixture),
                "motion_preferences": motion_preference_check(browser, fixture),
            }
            browser.close()
        (OUT / "geometry-report.json").write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )
    finally:
        fixture.close()


if __name__ == "__main__":
    main()
