"""Open Instagram login in the same Playwright browser the automation uses.

Log in manually (solve any CAPTCHA / email verification yourself), then
press Enter in this terminal.  The script saves your session cookies to
a JSON file that the worker can reload on future runs.

Usage:
    python warm_session.py <username>
"""

import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

COOKIE_DIR = os.path.join("data", "sessions")


def main():
    if len(sys.argv) < 2:
        print("Usage: python warm_session.py <instagram_username>")
        sys.exit(1)

    username = sys.argv[1]
    os.makedirs(COOKIE_DIR, exist_ok=True)
    cookie_path = os.path.join(COOKIE_DIR, f"{username}.json")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = context.new_page()
        page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")

        print()
        print("=" * 60)
        print("  Log in manually in the browser window.")
        print("  Solve any CAPTCHA or email verification.")
        print("  Once you see your Instagram feed, come back here")
        print("  and press ENTER to save the session.")
        print("=" * 60)
        input()

        cookies = context.cookies()
        with open(cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)

        has_session = any(
            c["name"] == "sessionid" and c.get("value") for c in cookies
        )
        if has_session:
            print(f"Session saved to {cookie_path} ({len(cookies)} cookies)")
        else:
            print("WARNING: No sessionid cookie found. Login may not have completed.")

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
