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


def approval_capture(browser, fixture) -> dict:
    page = browser.new_page(viewport={"width": 1672, "height": 941})
    page.goto(fixture.summon_approval_url, wait_until="networkidle")
    page.wait_for_function(
        "() => !document.querySelector('#approvalPanel')?.classList.contains('hidden')"
    )
    approval = rect(page, "#approvalPanel")
    right = rect(page, ".activity-sidebar")
    conversation = rect(page, ".conversation-workspace")
    buttons = page.locator("#approvalActions button")
    assert buttons.count() == 4
    for index in range(buttons.count()):
        box = buttons.nth(index).bounding_box()
        assert box is not None
        assert box["x"] >= approval["x"] - 1
        assert box["x"] + box["width"] <= approval["x"] + approval["width"] + 1
    assert conversation["x"] + conversation["width"] <= right["x"] + 2
    page.screenshot(path=str(OUT / "desktop-summon-approval.png"), full_page=True)
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
    page.screenshot(path=str(OUT / "desktop-offline.png"), full_page=True)
    page.close()
    return {"status_color": status_color, "core_opacity": core_opacity}


def mobile_approval_capture(browser, fixture) -> dict:
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(fixture.summon_approval_url, wait_until="networkidle")
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
    for index in range(buttons.count()):
        box = buttons.nth(index).bounding_box()
        assert box is not None
        assert box["x"] >= -1
        assert box["x"] + box["width"] <= 391
    page.screenshot(path=str(OUT / "mobile-approval-390x844.png"), full_page=False)
    page.close()
    return {"approval": approval, "right": right}


def reduced_motion_check(browser, fixture) -> dict:
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.emulate_media(reduced_motion="reduce")
    page.goto(fixture.review_url, wait_until="networkidle")
    wait_review(page)
    animation = page.locator(".core-halo-outer").evaluate(
        "(el) => getComputedStyle(el).animationName"
    )
    page.close()
    assert animation == "none"
    return {"core_halo_animation": animation}


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
                "summon_approval": approval_capture(browser, fixture),
                "offline": offline_capture(browser, fixture),
                "mobile_approval": mobile_approval_capture(browser, fixture),
                "reduced_motion": reduced_motion_check(browser, fixture),
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
