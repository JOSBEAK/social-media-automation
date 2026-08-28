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
        'input[type="password"]',
        'input[autocomplete="current-password"]',
    )
    LOGIN_SELECTORS = (
        'div[aria-label="Log in"][role="button"]',
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
            print("[InstagramAuth] Navigating to login page", flush=True)
            page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
            time.sleep(random.uniform(3, 5))

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
                return AuthenticationResult(False, "Instagram username field was not found")
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
                return AuthenticationResult(False, "Instagram password field was not found")
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
                    return AuthenticationResult(
                        False, f"Instagram login button and form were not available: {exc}"
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
                return AuthenticationResult(False, "Instagram requires a challenge or 2FA")

            if "accounts/onetap" in final_url_lower or "save" in page.content().lower():
                self._dismiss_save_login_info(page)

            if self._has_session(page):
                print("[InstagramAuth] sessionid cookie established", flush=True)
                print("[InstagramAuth] Login successful", flush=True)
                return AuthenticationResult(True)

            page_text = page.content().lower()
            for message in self.ERROR_MESSAGES:
                if message.lower() in page_text:
                    return AuthenticationResult(False, f"Instagram login rejected: {message}")

            if "accounts/login" in page.url.lower():
                return AuthenticationResult(
                    False,
                    "Instagram remained on the login page; credentials may be invalid or login was blocked",
                )

            return AuthenticationResult(
                False,
                "Instagram redirected after login but did not establish a sessionid cookie",
            )
        except Exception as exc:
            return AuthenticationResult(False, f"Instagram login error: {type(exc).__name__}: {exc}")

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
