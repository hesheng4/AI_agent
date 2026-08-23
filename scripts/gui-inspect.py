#!/usr/bin/env python3
"""Inspect the DeepSeek Harness Web GUI model picker and Models settings page."""
import time

from playwright.sync_api import sync_playwright

OUT = r"D:\AI_agent\debug_sessions"
BASE = "http://127.0.0.1:63340"


def dump(where, text):
    print("=" * 20, where, "=" * 20)
    print(text[:6000])


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    console_msgs = []
    page.on("console", lambda m: console_msgs.append(f"[{m.type}] {m.text[:300]}"))
    page.on("pageerror", lambda e: console_msgs.append(f"[pageerror] {str(e)[:300]}"))

    page.goto(BASE, timeout=60000)
    page.wait_for_load_state("networkidle", timeout=60000)
    time.sleep(3)
    page.screenshot(path=f"{OUT}\\gui-home.png", full_page=False)

    # 1) Find the composer model picker seat
    try:
        page.locator("textarea, [contenteditable='true']").first.click(timeout=8000)
        time.sleep(0.5)
        page.screenshot(path=f"{OUT}\\gui-composer-focused.png")
    except Exception as e:
        dump("composer focus", f"failed: {e}")

    # look for any element whose text mentions the current model or a picker button
    for sel in ["[data-model]", "[data-testid*=model]", "button", "[role=button]"]:
        try:
            els = page.locator(sel).all()
            hits = []
            for el in els[:80]:
                try:
                    t = (el.inner_text(timeout=1000) or "").strip().replace("\n", " | ")
                    if t and ("model" in t.lower() or "deepseek" in t.lower() or "provider" in t.lower() or "flash" in t.lower() or "atom" in t.lower() or "coding" in t.lower()):
                        hits.append(f"{sel} -> {t[:150]}")
                except Exception:
                    pass
            if hits:
                dump(f"candidate picker elements ({sel})", "\n".join(hits[:20]))
        except Exception:
            pass

    # 2) Open settings: look for a settings gear / "Settings" nav entry
    clicked_settings = False
    for sel in ['[aria-label*="Setting" i]', 'text=Settings', 'text=设置', '[title*="Setting" i]', 'button:has-text("设置")']:
        try:
            page.locator(sel).first.click(timeout=4000)
            clicked_settings = True
            dump("settings nav", f"clicked {sel}")
            break
        except Exception:
            continue
    time.sleep(1.5)
    page.screenshot(path=f"{OUT}\\gui-settings.png")

    # 3) Find the Models page entry and open it
    for sel in ['text=Models', 'text=模型', '[data-testid*=model]', 'a:has-text("Model")', 'button:has-text("Model")']:
        try:
            page.locator(sel).first.click(timeout=4000)
            dump("models page nav", f"clicked {sel}")
            break
        except Exception:
            continue
    time.sleep(2)
    page.screenshot(path=f"{OUT}\\gui-models.png", full_page=True)
    dump("models page body", page.locator("body").inner_text(timeout=5000)[:6000])

    dump("console", "\n".join(console_msgs[-40:]))
    browser.close()
