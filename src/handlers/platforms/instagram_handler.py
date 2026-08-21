import random
import time

from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.config.settings import Settings
from src.domains.authentication_result import AuthenticationResult
from src.domains.platform import Platform
from src.interfaces.i_platform_handler import IPlatformHandler


class InstagramHandler(IPlatformHandler):
    BASE_URL = "https://www.instagram.com/"
    LOGIN_URL = "https://www.instagram.com/accounts/login/"
    USERNAME_SELECTORS = (
        (By.NAME, "username"),
        (By.NAME, "email"),
        (By.CSS_SELECTOR, 'input[type="text"]'),
        (By.CSS_SELECTOR, 'input[autocomplete="username"]'),
    )
    PASSWORD_SELECTORS = (
        (By.NAME, "password"),
        (By.CSS_SELECTOR, 'input[type="password"]'),
        (By.CSS_SELECTOR, 'input[autocomplete="current-password"]'),
    )
    LOGIN_SELECTORS = (
        (By.XPATH, '//div[@aria-label="Log in" and @role="button"]'),
        (By.XPATH, '//button[@type="submit"]'),
        (By.XPATH, '//button[text()="Log in"]'),
        (By.XPATH, '//button[contains(text(), "Log in")]'),
        (By.CSS_SELECTOR, 'button[type="submit"]'),
        (By.CSS_SELECTOR, "button._acan"),
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
    def _find_first(driver, selectors, timeout: float):
        for by, selector in selectors:
            try:
                element = WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((by, selector))
                )
                print(f"[InstagramAuth] Found element using {by}={selector}", flush=True)
                return element
            except TimeoutException:
                continue
        return None

    @staticmethod
    def _type_humanly(element, value: str) -> None:
        element.click()
        time.sleep(0.5)
        element.clear()
        time.sleep(0.5)
        for character in value:
            element.send_keys(character)
            time.sleep(random.uniform(Settings.LOGIN_TYPING_MIN, Settings.LOGIN_TYPING_MAX))

    def login(self, driver, account) -> AuthenticationResult:
        try:
            print("[InstagramAuth] Navigating to login page", flush=True)
            driver.get(self.LOGIN_URL)
            time.sleep(random.uniform(3, 5))

            current_url = driver.current_url.lower()
            print(f"[InstagramAuth] Login page URL: {driver.current_url}", flush=True)
            if (
                "accounts/login" not in current_url
                and "accounts" not in current_url
                and self._has_session(driver)
            ):
                print("[InstagramAuth] Existing authenticated session detected", flush=True)
                return AuthenticationResult(True)

            username_field = self._find_first(driver, self.USERNAME_SELECTORS, 3)
            if username_field is None:
                return AuthenticationResult(False, "Instagram username field was not found")
            self._type_humanly(username_field, account.username)
            print("[InstagramAuth] Username entered", flush=True)

            password_field = self._find_first(driver, self.PASSWORD_SELECTORS, 2)
            if password_field is None:
                try:
                    next_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, '//div[text()="Next"]'))
                    )
                    next_button.click()
                    time.sleep(2)
                    password_field = self._find_first(driver, self.PASSWORD_SELECTORS, 3)
                except TimeoutException:
                    pass
            if password_field is None:
                return AuthenticationResult(False, "Instagram password field was not found")
            self._type_humanly(password_field, account.password)
            print("[InstagramAuth] Password entered", flush=True)

            login_button = None
            selected_login_selector = None
            for by, selector in self.LOGIN_SELECTORS:
                try:
                    login_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    selected_login_selector = f"{by}={selector}"
                    break
                except TimeoutException:
                    continue

            if login_button is None:
                try:
                    form = driver.find_element(By.TAG_NAME, "form")
                    driver.execute_script("arguments[0].submit();", form)
                    print("[InstagramAuth] Submitted login form with JavaScript", flush=True)
                except Exception as exc:
                    return AuthenticationResult(
                        False, f"Instagram login button and form were not available: {exc}"
                    )
            else:
                try:
                    login_button.click()
                except ElementClickInterceptedException:
                    driver.execute_script("arguments[0].click();", login_button)
                print(
                    f"[InstagramAuth] Clicked login using {selected_login_selector}",
                    flush=True,
                )

            print("[InstagramAuth] Waiting for Instagram login response", flush=True)
            time.sleep(Settings.LOGIN_SETTLE_SECONDS)
            final_url = driver.current_url
            final_url_lower = final_url.lower()
            print(f"[InstagramAuth] Final URL: {final_url}", flush=True)
            if "challenge" in final_url_lower:
                return AuthenticationResult(False, "Instagram requires a challenge or 2FA")

            if "accounts/onetap" in final_url_lower or "save" in driver.page_source.lower():
                self._dismiss_save_login_info(driver)

            if self._has_session(driver):
                print("[InstagramAuth] sessionid cookie established", flush=True)
                print("[InstagramAuth] Login successful", flush=True)
                return AuthenticationResult(True)

            page_text = driver.page_source.lower()
            for message in self.ERROR_MESSAGES:
                if message.lower() in page_text:
                    return AuthenticationResult(False, f"Instagram login rejected: {message}")

            if "accounts/login" in driver.current_url.lower():
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
    def _has_session(driver) -> bool:
        session_cookie = driver.get_cookie("sessionid")
        return bool(session_cookie and session_cookie.get("value"))

    @staticmethod
    def _dismiss_save_login_info(driver) -> None:
        selectors = (
            (By.XPATH, '//button[normalize-space()="Not now"]'),
            (By.XPATH, '//div[@role="button" and normalize-space()="Not now"]'),
            (By.XPATH, '//*[normalize-space()="Not now"]'),
        )
        for by, selector in selectors:
            try:
                button = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((by, selector))
                )
                button.click()
                print("[InstagramAuth] Completed 'Save login info' screen", flush=True)
                time.sleep(2)
                return
            except TimeoutException:
                continue
        print("[InstagramAuth] Save-login screen had no 'Not now' control", flush=True)
