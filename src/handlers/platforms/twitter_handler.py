from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.domains.platform import Platform
from src.interfaces.i_platform_handler import IPlatformHandler


class TwitterHandler(IPlatformHandler):
    """Browser adapter for X (Twitter). X-specific selectors live only here/actions."""

    LOGIN_URL = "https://x.com/i/flow/login"

    @property
    def platform(self) -> Platform:
        return Platform.TWITTER

    def get_post_url(self, identifier: str) -> str:
        identifier = identifier.strip("/")
        if "/status/" in identifier:
            return f"https://x.com/{identifier}"
        raise ValueError("X post identifiers must include '<username>/status/<post_id>'")

    def login(self, driver, account) -> bool:
        wait = WebDriverWait(driver, 20)
        try:
            driver.get(self.LOGIN_URL)
            username = wait.until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, 'input[autocomplete="username"]')
                )
            )
            username.send_keys(account.username)
            wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[.//span[text()="Next"]]'))
            ).click()

            try:
                password = WebDriverWait(driver, 8).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[name="password"]'))
                )
            except TimeoutException:
                challenge = wait.until(
                    EC.visibility_of_element_located(
                        (By.CSS_SELECTOR, 'input[data-testid="ocfEnterTextTextInput"]')
                    )
                )
                identifier = account.verification_identifier or account.username
                challenge.send_keys(identifier)
                wait.until(
                    EC.element_to_be_clickable((By.XPATH, '//button[.//span[text()="Next"]]'))
                ).click()
                password = wait.until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[name="password"]'))
                )

            password.send_keys(account.password)
            wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[data-testid="LoginForm_Login_Button"]')
                )
            ).click()
            wait.until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'a[data-testid="AppTabBar_Home_Link"]')),
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href="/home"]')),
                )
            )
            print("[Twitter] ✅ Login success")
            return True
        except Exception as exc:
            print(f"[Twitter] Login error: {str(exc)[:160]}")
            return False
