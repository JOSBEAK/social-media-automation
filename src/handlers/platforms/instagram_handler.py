import os
import random
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout

from src.config.settings import Settings
from src.domains.authentication_result import AuthenticationResult
from src.domains.platform import Platform
from src.interfaces.i_platform_handler import IPlatformHandler


class InstagramHandler(IPlatformHandler):
    BASE_URL = "https://www.instagram.com/"
    LOGIN_URL = "https://www.instagram.com/accounts/login/"
    USERNAME_SELECTORS = (
        'input[name="username"]',
        'input[name="email"]',
        'input[type="text"]',
        'input[autocomplete="username"]',
    )
    PASSWORD_SELECTORS = (
        'input[name="password"]',
        'input[name="pass"]',
        'input[type="password"]',
        'input[autocomplete="current-password"]',
    )
    LOGIN_SELECTORS = (
        'div[aria-label="Log In"][role="button"]',
        'div[aria-label="Log in"][role="button"]',
        'div[role="button"]:has-text("Log in")',
        'button[type="submit"]',
        'button:has-text("Log in")',
        'button._acan',
    )
    ERROR_MESSAGES = (
        "Sorry, your password was incorrect",
        "Please enter a valid",
        "Your account is temporarily locked",
        "We detected an unusual login",
        "Check your email",
        "Enter the confirmation code",
    )

    # Maps known error substrings to failure classifications
    _ERROR_CLASSIFICATIONS = {
        "sorry, your password was incorrect": "INVALID_CREDENTIALS",
        "please enter a valid": "INVALID_CREDENTIALS",
        "your account is temporarily locked": "LOGIN_CHALLENGE",
        "we detected an unusual login": "LOGIN_CHALLENGE",
        "check your email": "CAPTCHA_OR_VERIFICATION",
        "enter the confirmation code": "CAPTCHA_OR_VERIFICATION",
        "suspicious login attempt": "LOGIN_CHALLENGE",
        "verify your identity": "CAPTCHA_OR_VERIFICATION",
        "confirm your identity": "CAPTCHA_OR_VERIFICATION",
        "security code": "CAPTCHA_OR_VERIFICATION",
        "two-factor": "CAPTCHA_OR_VERIFICATION",
    }

    SCREENSHOT_DIR = os.path.join("debug", "login_failures")

    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    def get_post_url(self, identifier: str) -> str:
        return f"https://www.instagram.com/p/{identifier}/"

    @staticmethod
    def _find_first(page, selectors, timeout: float = 3000):
        """Try each CSS selector and return the first visible element, or None."""
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                locator.wait_for(state="visible", timeout=timeout)
                print(f"[InstagramAuth] Found element using {selector}", flush=True)
                return locator
            except PlaywrightTimeout:
                continue
        return None

    @staticmethod
    def _type_humanly(locator, value: str) -> None:
        locator.click()
        time.sleep(0.5)
        locator.fill("")
        time.sleep(0.5)
        for character in value:
            locator.press_sequentially(character, delay=random.uniform(
                Settings.LOGIN_TYPING_MIN * 1000, Settings.LOGIN_TYPING_MAX * 1000
            ))

    def login(self, page, account) -> AuthenticationResult:
        try:
            # Load saved session cookies if available (from warm_session.py)
            self._load_saved_cookies(page, account.username)

            print("[InstagramAuth] Navigating to login page", flush=True)
            page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
            time.sleep(random.uniform(3, 5))

            # Dismiss cookie consent banner if present (blocks form in some regions)
            self._dismiss_cookie_banner(page)

            current_url = page.url.lower()
            print(f"[InstagramAuth] Login page URL: {page.url}", flush=True)
            if (
                "accounts/login" not in current_url
                and "accounts" not in current_url
                and self._has_session(page)
            ):
                print("[InstagramAuth] Existing authenticated session detected", flush=True)
                return AuthenticationResult(True)

            username_field = self._find_first(page, self.USERNAME_SELECTORS, 3000)
            if username_field is None:
                return self._diagnose_and_fail(page, account, "Instagram username field was not found")
            self._type_humanly(username_field, account.username)
            print("[InstagramAuth] Username entered", flush=True)

            password_field = self._find_first(page, self.PASSWORD_SELECTORS, 2000)
            if password_field is None:
                try:
                    next_button = page.locator('div:has-text("Next")')
                    next_button.first.click(timeout=3000)
                    time.sleep(2)
                    password_field = self._find_first(page, self.PASSWORD_SELECTORS, 3000)
                except PlaywrightTimeout:
                    pass
            if password_field is None:
                return self._diagnose_and_fail(page, account, "Instagram password field was not found")
            self._type_humanly(password_field, account.password)
            print("[InstagramAuth] Password entered", flush=True)

            login_button = None
            selected_login_selector = None
            for selector in self.LOGIN_SELECTORS:
                try:
                    locator = page.locator(selector).first
                    locator.wait_for(state="visible", timeout=5000)
                    login_button = locator
                    selected_login_selector = selector
                    break
                except PlaywrightTimeout:
                    continue

            if login_button is None:
                try:
                    page.evaluate("document.querySelector('form')?.submit()")
                    print("[InstagramAuth] Submitted login form with JavaScript", flush=True)
                except Exception as exc:
                    return self._diagnose_and_fail(
                        page, account,
                        f"Instagram login button and form were not available: {exc}",
                    )
            else:
                try:
                    login_button.click()
                except Exception:
                    page.evaluate("arguments => arguments[0].click()", login_button.element_handle())
                print(
                    f"[InstagramAuth] Clicked login using {selected_login_selector}",
                    flush=True,
                )

            print("[InstagramAuth] Waiting for Instagram login response", flush=True)
            time.sleep(Settings.LOGIN_SETTLE_SECONDS)
            final_url = page.url
            final_url_lower = final_url.lower()
            print(f"[InstagramAuth] Final URL: {final_url}", flush=True)
            if "challenge" in final_url_lower:
                return self._diagnose_and_fail(
                    page, account,
                    "Instagram requires a challenge or 2FA",
                )

            if "accounts/onetap" in final_url_lower or "save" in page.content().lower():
                self._dismiss_save_login_info(page)

            if self._has_session(page):
                print("[InstagramAuth] sessionid cookie established", flush=True)
                print("[InstagramAuth] LOGIN_SUCCESS", flush=True)
                return AuthenticationResult(True)

            # Login did not succeed -- run full diagnostics
            return self._diagnose_and_fail(page, account, None)

        except Exception as exc:
            return self._diagnose_and_fail_safe(
                page, account,
                f"Instagram login error: {type(exc).__name__}: {exc}",
            )

    # ------------------------------------------------------------------
    # Diagnostics helpers
    # ------------------------------------------------------------------

    def _diagnose_and_fail(self, page, account, fallback_message: str | None) -> AuthenticationResult:
        """Inspect the page to classify and log the login failure, capture a
        screenshot, and return an ``AuthenticationResult`` with the diagnosis."""
        try:
            return self._run_diagnostics(page, account, fallback_message)
        except Exception as diag_exc:
            # Diagnostics themselves must never crash the worker
            msg = fallback_message or "Unknown login failure"
            print(
                f"[InstagramAuth] LOGIN_FAILED diagnostics error: "
                f"{type(diag_exc).__name__}: {diag_exc}",
                flush=True,
            )
            return AuthenticationResult(False, msg)

    def _diagnose_and_fail_safe(self, page, account, fallback_message: str) -> AuthenticationResult:
        """Like ``_diagnose_and_fail`` but also guards against page being None
        (e.g. after an exception during navigation)."""
        if page is None:
            print(f"[InstagramAuth] LOGIN_FAILED {fallback_message}", flush=True)
            return AuthenticationResult(False, fallback_message)
        return self._diagnose_and_fail(page, account, fallback_message)

    def _run_diagnostics(self, page, account, fallback_message: str | None) -> AuthenticationResult:
        """Core diagnostic routine: inspects the page, classifies the failure,
        captures a screenshot, and logs everything."""
        current_url = page.url
        page_title = page.title()
        page_text = page.content().lower()

        # --- Detect visible Instagram error/message text ---
        detected_error_text = None
        for message in self.ERROR_MESSAGES:
            if message.lower() in page_text:
                detected_error_text = message
                break

        # Also try to extract any visible error banners
        if detected_error_text is None:
            for selector in (
                '#slfErrorAlert',
                'div[role="alert"]',
                'p[data-testid="login-error-message"]',
                'div[class*="error"]',
            ):
                try:
                    el = page.locator(selector).first
                    el.wait_for(state="visible", timeout=1000)
                    text = el.inner_text(timeout=1000).strip()
                    if text:
                        detected_error_text = text[:200]
                        break
                except (PlaywrightTimeout, Exception):
                    continue

        # --- Check field / button visibility ---
        username_visible = self._is_any_visible(page, self.USERNAME_SELECTORS)
        password_visible = self._is_any_visible(page, self.PASSWORD_SELECTORS)
        login_button_visible = self._is_any_visible(page, self.LOGIN_SELECTORS)

        # --- Classify ---
        classification = self._classify_failure(
            current_url, page_text, detected_error_text,
            username_visible, password_visible,
        )

        # --- Build descriptive error message ---
        if detected_error_text:
            error_description = f"Instagram login rejected: {detected_error_text}"
        elif fallback_message:
            error_description = fallback_message
        elif classification == "LOGIN_PAGE_STILL_VISIBLE":
            error_description = (
                "Instagram remained on the login page after submission; "
                "credentials may be invalid or login was blocked"
            )
        else:
            error_description = f"Instagram login failure: {classification}"

        # --- Log diagnostics (never log passwords) ---
        print(
            f"[InstagramAuth] LOGIN_FAILED\n"
            f"  account:             {account.username}\n"
            f"  url:                 {current_url}\n"
            f"  page_title:          {page_title}\n"
            f"  detected_error_text: {detected_error_text or '(none)'}\n"
            f"  username_field:      {'visible' if username_visible else 'not visible'}\n"
            f"  password_field:      {'visible' if password_visible else 'not visible'}\n"
            f"  login_button:        {'visible' if login_button_visible else 'not visible'}\n"
            f"  classification:      {classification}\n"
            f"  error:               {error_description}",
            flush=True,
        )

        # --- Screenshot ---
        self._capture_screenshot(page, account.username)

        return AuthenticationResult(False, f"[{classification}] {error_description}")

    @classmethod
    def _classify_failure(
        cls, url: str, page_text: str, detected_error: str | None,
        username_visible: bool, password_visible: bool,
    ) -> str:
        """Return one of the standard classification labels."""
        url_lower = url.lower()

        # Check for challenge / 2FA / captcha URLs first
        if "challenge" in url_lower:
            return "LOGIN_CHALLENGE"
        if "recaptcha" in url_lower or "captcha" in url_lower:
            return "CAPTCHA_OR_VERIFICATION"

        # Check detected error text against classification map
        if detected_error:
            error_lower = detected_error.lower()
            for pattern, label in cls._ERROR_CLASSIFICATIONS.items():
                if pattern in error_lower:
                    return label

        # Broader page-text checks for challenge/captcha indicators
        challenge_indicators = (
            "suspicious login attempt", "verify your identity",
            "confirm your identity", "security code", "two-factor",
            "enter the code", "we sent a code",
        )
        for indicator in challenge_indicators:
            if indicator in page_text:
                return "CAPTCHA_OR_VERIFICATION"

        # If login fields are still on screen, the form was never accepted
        if "accounts/login" in url_lower and (username_visible or password_visible):
            return "LOGIN_PAGE_STILL_VISIBLE"

        # Timeout-like: no error text, no fields, no known redirect
        if not detected_error and not username_visible and not password_visible:
            if "accounts/login" in url_lower:
                return "TIMEOUT"

        return "UNKNOWN_LOGIN_FAILURE"

    @staticmethod
    def _is_any_visible(page, selectors: tuple, timeout: float = 500) -> bool:
        """Return True if any of the selectors match a currently visible element."""
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                locator.wait_for(state="visible", timeout=timeout)
                return True
            except (PlaywrightTimeout, Exception):
                continue
        return False

    def _capture_screenshot(self, page, account_username: str) -> None:
        """Save a debug screenshot. Filenames use the account username only
        (never passwords or secrets)."""
        try:
            os.makedirs(self.SCREENSHOT_DIR, exist_ok=True)
            # Sanitise username for filesystem safety
            safe_name = "".join(
                c if c.isalnum() or c in ("_", "-", ".") else "_"
                for c in account_username
            )
            path = os.path.join(self.SCREENSHOT_DIR, f"{safe_name}.png")
            page.screenshot(path=path, full_page=True)
            print(f"[InstagramAuth] Screenshot saved: {path}", flush=True)
        except Exception as exc:
            print(
                f"[InstagramAuth] Screenshot capture failed: {type(exc).__name__}: {exc}",
                flush=True,
            )

    @staticmethod
    def _has_session(page) -> bool:
        cookies = page.context.cookies("https://www.instagram.com")
        return any(c["name"] == "sessionid" and c.get("value") for c in cookies)

    @staticmethod
    def _dismiss_save_login_info(page) -> None:
        selectors = (
            'button:has-text("Not now")',
            'div[role="button"]:has-text("Not now")',
            ':has-text("Not now")',
        )
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                locator.click(timeout=3000)
                print("[InstagramAuth] Completed 'Save login info' screen", flush=True)
                time.sleep(2)
                return
            except PlaywrightTimeout:
                continue
        print("[InstagramAuth] Save-login screen had no 'Not now' control", flush=True)

    @staticmethod
    def _dismiss_cookie_banner(page) -> None:
        """Dismiss Instagram/Meta cookie consent banners if present."""
        cookie_selectors = (
            'button:has-text("Allow all cookies")',
            'button:has-text("Allow essential and optional cookies")',
            'button:has-text("Accept")',
            'button:has-text("Accept All")',
        )
        for selector in cookie_selectors:
            try:
                locator = page.locator(selector).first
                locator.click(timeout=2000)
                print(f"[InstagramAuth] Dismissed cookie banner: {selector}", flush=True)
                time.sleep(1)
                return
            except (PlaywrightTimeout, Exception):
                continue

    @staticmethod
    def _load_saved_cookies(page, username: str) -> None:
        """Load cookies saved by warm_session.py into the browser context."""
        import json as _json
        cookie_path = os.path.join("data", "sessions", f"{username}.json")
        if not os.path.isfile(cookie_path):
            return
        try:
            with open(cookie_path, "r", encoding="utf-8") as f:
                cookies = _json.load(f)
            page.context.add_cookies(cookies)
            print(
                f"[InstagramAuth] Loaded {len(cookies)} saved cookies for {username}",
                flush=True,
            )
        except Exception as exc:
            print(
                f"[InstagramAuth] Could not load saved cookies: {type(exc).__name__}: {exc}",
                flush=True,
            )
