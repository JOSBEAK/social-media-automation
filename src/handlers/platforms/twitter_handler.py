from playwright.sync_api import TimeoutError as PlaywrightTimeout

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

    def login(self, page, account) -> bool:
        try:
            page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
            username = page.locator('input[autocomplete="username"]')
            username.wait_for(state="visible", timeout=20000)
            username.fill(account.username)
            page.locator('button:has(span:text("Next"))').click()

            try:
                password = page.locator('input[name="password"]')
                password.wait_for(state="visible", timeout=8000)
            except PlaywrightTimeout:
                challenge = page.locator('input[data-testid="ocfEnterTextTextInput"]')
                challenge.wait_for(state="visible", timeout=20000)
                identifier = account.verification_identifier or account.username
                challenge.fill(identifier)
                page.locator('button:has(span:text("Next"))').click()
                password = page.locator('input[name="password"]')
                password.wait_for(state="visible", timeout=20000)

            password.fill(account.password)
            page.locator('button[data-testid="LoginForm_Login_Button"]').click()
            # Wait for home page indicator
            page.locator(
                'a[data-testid="AppTabBar_Home_Link"], a[href="/home"]'
            ).first.wait_for(state="visible", timeout=20000)
            print("[Twitter] LOGIN_SUCCESS")
            return True
        except Exception as exc:
            print(f"[Twitter] Login error: {str(exc)[:160]}")
            return False
