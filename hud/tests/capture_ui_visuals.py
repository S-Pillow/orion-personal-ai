from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright

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
    page.locator("#transcript").evaluate("(el) => { el.scrollTop = 0; }")
    page.wait_for_timeout(75)
    assert page.locator("#transcript").evaluate("(el) => el.scrollTop") == 0
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
    page.locator("#transcript").evaluate("(el) => { el.scrollTop = 0; }")
    page.wait_for_timeout(75)
    assert page.locator("#transcript").evaluate("(el) => el.scrollTop") == 0
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


def core_renderer_capture(browser, fixture) -> dict:
    # Freeze JS timers for pose captures: the closed hold is only 30ms, shorter
    # than screenshot stabilization. Record normal-speed motion separately.
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.clock.install(time=datetime(2025, 4, 28, 22, 23, tzinfo=timezone.utc))
    page.goto(fixture.core_review_url, wait_until="networkidle")
    page.wait_for_function("() => Boolean(window.__orionCoreFixture)")
    page.clock.pause_at(datetime(2025, 4, 28, 22, 24, tzinfo=timezone.utc))
    page.evaluate("() => { window.__orionCoreFixture.state('OFFLINE'); window.__orionCoreFixture.neutral(); }")

    def snapshot(name: str) -> dict:
        state = page.evaluate("() => window.__orionCoreFixture.snapshot()")
        # Complete finite CSS transitions to their current target without
        # letting the controller advance to another blink phase.
        png = page.screenshot(path=str(OUT / f"core-{name}.png"), animations="disabled")
        assert page.evaluate("() => window.__orionCoreFixture.snapshot()") == state
        # CSS can break the fixed-aperture architecture even when SVG references
        # are intact. Check both eyes' stationary layers in every captured pose.
        fixed_transforms = page.locator(
            ".core-eye-system, .core-eye-shutter, .core-eye-aperture, "
            ".core-eye-window, clipPath[id^='coreEyeClip']"
        ).evaluate_all("nodes => nodes.map(node => getComputedStyle(node).transform)")
        assert len(fixed_transforms) == 10
        assert all(transform == "none" for transform in fixed_transforms), fixed_transforms
        reflection_fills = page.locator(".core-glass-reflection").evaluate_all(
            "nodes => nodes.map(node => getComputedStyle(node).fill)"
        )
        assert reflection_fills and all(fill == "none" for fill in reflection_fills)
        orb = rect(page, ".core-orb")
        scale = orb["width"] / 320
        eye_box = tuple(round(v) for v in (
            orb["x"] + 80 * scale, orb["y"] + 136 * scale,
            orb["x"] + 240 * scale, orb["y"] + 176 * scale,
        ))
        pixels = Image.open(BytesIO(png)).convert("RGB").crop(eye_box)
        state["bright_eye_pixels"] = sum(g > 150 and b > 170 for r, g, b in pixels.getdata())
        # Measure the light that was actually drawn, not just its SVG transform.
        # A broad white wash can move in the DOM while the gaze remains unreadable.
        centers = []
        for x0, x1 in ((0, pixels.width // 2), (pixels.width // 2, pixels.width)):
            lit_x = [x for y in range(pixels.height) for x in range(x0, x1)
                     if pixels.getpixel((x, y))[1] > 150 and pixels.getpixel((x, y))[2] > 170]
            centers.append(sum(lit_x) / len(lit_x) if lit_x else None)
        state["eye_light_centers"] = centers
        return state

    neutral = snapshot("neutral")
    assert neutral["state"] == "READY"
    assert neutral["gaze"] == "forward"
    assert neutral["blinkPhase"] == "open"
    assert neutral["bright_eye_pixels"] > 50, neutral
    def aperture_rects():
        return [rect(page, f".core-eye-{side} .core-eye-aperture") for side in ("left", "right")]

    apertures = aperture_rects()

    page.evaluate("() => window.__orionCoreFixture.gaze('left')")
    left = snapshot("gaze-left")
    left_focus = rect(page, ".core-eye-left .core-eye-focus")
    assert left["gaze"] == "left"
    assert aperture_rects() == apertures

    page.evaluate("() => window.__orionCoreFixture.gaze('right')")
    right = snapshot("gaze-right")
    right_focus = rect(page, ".core-eye-left .core-eye-focus")
    assert right["gaze"] == "right"
    assert aperture_rects() == apertures
    travel = (right_focus["x"] - left_focus["x"]) / apertures[0]["width"]
    assert .2 < travel < .35, travel
    for index, aperture in enumerate(apertures):
        visible_travel = (right["eye_light_centers"][index] - left["eye_light_centers"][index]) / aperture["width"]
        assert .18 < visible_travel < .35, visible_travel

    page.evaluate("() => window.__orionCoreFixture.gaze('left')")
    assert page.evaluate("() => window.__orionCoreFixture.blink()") is True
    page.clock.run_for(80)
    closed = snapshot("blink-closed")
    assert closed["blinkPhase"] == "closed"
    assert closed["gaze"] == "left"
    assert aperture_rects() == apertures
    # Tests the rendered output, including glow: checking a class alone missed
    # the previous bright-eye leak in the purported closed frame.
    assert closed["bright_eye_pixels"] < neutral["bright_eye_pixels"] * .12, closed

    page.clock.run_for(30)
    assert page.evaluate("() => window.__orionCoreFixture.snapshot().blinkPhase") == "opening"
    page.clock.run_for(140)
    reopened = snapshot("blink-reopened")
    assert reopened["blinkPhase"] == "open"
    assert reopened["gaze"] == "left"
    assert reopened["bright_eye_pixels"] > neutral["bright_eye_pixels"] * .8

    page.evaluate("() => window.__orionCoreFixture.state('WAITING')")
    waiting = snapshot("waiting")
    assert waiting["state"] == "WAITING"

    assert page.evaluate("() => window.__orionCoreFixture.blink()") is True
    page.clock.run_for(80)
    page.evaluate("() => window.__orionCoreFixture.state('THINKING')")
    page.clock.run_for(170)
    after_state_change = page.evaluate("() => window.__orionCoreFixture.snapshot()")
    assert after_state_change["state"] == "THINKING"
    assert after_state_change["blinkPhase"] == "open"

    assert page.evaluate("() => window.__orionCoreFixture.blink()") is True
    page.clock.run_for(80)
    page.evaluate("() => window.__orionCoreFixture.state('OFFLINE')")
    offline = snapshot("offline")
    assert offline["state"] == "OFFLINE"
    assert offline["gaze"] == "forward"
    assert offline["blinkPhase"] == "open"

    page.evaluate("() => window.__orionCoreFixture.neutral()")
    assert page.evaluate("() => window.__orionCoreFixture.blink()") is True
    page.clock.run_for(80)
    page.emulate_media(reduced_motion="reduce")
    # Media-query change events are delivered independently of the fake clock.
    expect(page.locator("#coreStage")).to_have_attribute("data-motion", "reduced")
    reduced = snapshot("reduced-motion")
    assert reduced["motion"] == "reduced"
    assert reduced["blinkPhase"] == "open"
    assert reduced["gaze"] == "forward"
    assert page.evaluate("() => window.__orionCoreFixture.blink()") is False
    context.close()

    # This recording uses the unmodified production controller and real time.
    live = browser.new_context(
        viewport={"width": 1440, "height": 900},
        record_video_dir=str(OUT),
        record_video_size={"width": 1440, "height": 900},
    )
    page = live.new_page()
    page.goto(fixture.core_review_url, wait_until="networkidle")
    page.wait_for_function("() => Boolean(window.__orionCoreFixture)")
    page.wait_for_timeout(800)
    for gaze in ("left", "right", "forward"):
        page.evaluate("gaze => window.__orionCoreFixture.gaze(gaze)", gaze)
        page.wait_for_timeout(650)
        page.evaluate("() => window.__orionCoreFixture.blink()")
        page.wait_for_timeout(650)
    page.evaluate("() => window.__orionCoreFixture.state('WAITING')")
    page.wait_for_timeout(800)
    page.evaluate("() => window.__orionCoreFixture.neutral()")
    page.evaluate("() => window.__orionCoreFixture.attention('reply')")
    page.wait_for_timeout(900)
    page.evaluate("() => window.__orionCoreFixture.attention('approval')")
    page.wait_for_timeout(2200)
    page.evaluate("() => window.__orionCoreFixture.neutral()")
    page.wait_for_timeout(800)
    page.evaluate("() => window.__orionCoreFixture.attention('summon')")
    page.wait_for_timeout(1800)
    video = page.video
    page.close()
    video.save_as(str(OUT / "core-motion-review.webm"))
    live.close()

    return {
        "neutral": neutral, "left": left, "right": right, "closed": closed,
        "reopened": reopened, "waiting": waiting,
        "after_state_change": after_state_change, "offline": offline,
        "reduced_motion": reduced,
    }


def attention_capture(browser, fixture, width=1440, height=900) -> dict:
    page = browser.new_page(viewport={"width": width, "height": height})
    page.clock.install(time=datetime(2025, 4, 28, 22, 23, tzinfo=timezone.utc))
    page.goto(fixture.core_review_url, wait_until="networkidle")
    page.wait_for_function("() => Boolean(window.__orionCoreFixture)")
    page.clock.pause_at(datetime(2025, 4, 28, 22, 24, tzinfo=timezone.utc))
    page.evaluate("() => { window.__orionCoreFixture.state('OFFLINE'); window.__orionCoreFixture.neutral(); }")

    def snapshot(name):
        page.screenshot(path=str(OUT / f"core-attention-{name}-{width}.png"), animations="disabled")
        return page.evaluate("() => window.__orionCoreFixture.snapshot()")

    # These exercise the production stream, approval and summon hooks, not a
    # direct setGaze call. Their payloads are isolated presentation fixtures.
    page.evaluate("() => window.__orionCoreFixture.attention('reply')")
    reply = snapshot("reply")
    assert reply["gaze"] == "down", reply
    assert reply["attentionTarget"] == "transcript", reply
    page.evaluate("() => window.__orionCoreFixture.attention('approval')")
    approval = snapshot("approval")
    # On mobile the decision lives below the hero and scrolls the orb away.
    # There is no visible source/target pair; suppress attention in that case.
    expected_target = "approvalPanel" if width > 900 else None
    assert approval["gaze"] == ("right" if width > 900 else "forward"), approval
    assert approval["attentionTarget"] == expected_target, approval
    page.evaluate("() => window.__orionCoreFixture.attention('reply')")
    assert page.evaluate("() => window.__orionCoreFixture.snapshot().attentionTarget") == expected_target
    page.clock.run_for(1800)
    returned = snapshot("returned")
    assert returned["gaze"] == "forward"
    assert returned["attentionTarget"] is None
    page.evaluate("() => window.__orionCoreFixture.neutral()")
    page.evaluate("() => window.scrollTo({ top: 0, behavior: 'instant' })")
    page.clock.run_for(1000)
    page.evaluate("() => window.__orionCoreFixture.attention('summon')")
    summon = snapshot("summon")
    assert summon["gaze"] == "down", summon
    assert summon["attentionTarget"] == "summonPanel", summon
    page.emulate_media(reduced_motion="reduce")
    expect(page.locator("#coreStage")).to_have_attribute("data-motion", "reduced")
    page.evaluate("() => window.__orionCoreFixture.attention('approval')")
    assert page.evaluate("() => window.__orionCoreFixture.snapshot().gaze") == "forward"
    assert page.evaluate("() => window.__orionCoreFixture.snapshot().attentionTarget") is None
    page.close()
    return {"reply": reply, "approval": approval, "returned": returned, "summon": summon}


def welcome_capture(browser, fixture, width, height) -> dict:
    page = browser.new_page(viewport={"width": width, "height": height})
    page.goto(fixture.origin, wait_until="networkidle")
    expect(page.locator(".no-session")).to_be_visible()
    welcome = rect(page, ".conversation-workspace")
    composer = rect(page, ".composer")
    assert welcome["height"] <= 161
    assert composer["y"] + composer["height"] <= height
    page.screenshot(path=str(OUT / f"welcome-{width}.png"))
    page.locator("#sessionSelect").select_option("session_1")
    page.wait_for_function("() => document.querySelectorAll('.message').length > 0")
    assert page.locator(".no-session").count() == 0
    populated = rect(page, ".conversation-workspace")
    assert populated["height"] > welcome["height"]
    assert abs(rect(page, ".composer")["y"] - composer["y"]) < 1
    page.close()
    return {"welcome": welcome, "composer": composer, "populated": populated}


def main() -> None:
    fixture = UIConvergenceFixture()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            report = {
                "welcome_desktop": welcome_capture(browser, fixture, 1672, 941),
                "welcome_mobile": welcome_capture(browser, fixture, 390, 844),
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
                "core_renderer": core_renderer_capture(browser, fixture),
                "core_attention_desktop": attention_capture(browser, fixture),
                "core_attention_mobile": attention_capture(browser, fixture, 390, 844),
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
