import unittest
from unittest.mock import patch, MagicMock

from src.handlers.platforms.instagram_handler import InstagramHandler
from src.models.account import Account


class FakeLocator:
    def __init__(self, on_click=None, visible=True):
        self.value = ""
        self.on_click = on_click
        self._visible = visible

    @property
    def first(self):
        return self

    def click(self, **kwargs):
        if self.on_click:
            self.on_click()

    def fill(self, value):
        self.value = value

    def press_sequentially(self, char, delay=0):
        self.value += char

    def wait_for(self, **kwargs):
        if not self._visible:
            from playwright.sync_api import TimeoutError as PlaywrightTimeout
            raise PlaywrightTimeout("timeout")
        return self

    def element_handle(self):
        return MagicMock()


class FakeContext:
    def __init__(self):
        self._cookies = {}

    def cookies(self, url=None):
        return list(self._cookies.values())


class FakePage:
    def __init__(self):
        self.url = InstagramHandler.LOGIN_URL
        self._content = ""
        self.username = FakeLocator()
        self.password = FakeLocator()
        self.login_button = FakeLocator(self._login)
        self.context = FakeContext()
        self._locators = {
            'input[name="username"]': self.username,
            'input[name="password"]': self.password,
            'button[type="submit"]': self.login_button,
        }

    def _login(self):
        self.url = "https://www.instagram.com/accounts/onetap/"
        self.context._cookies["sessionid"] = {
            "name": "sessionid", "value": "test-session"
        }

    def goto(self, url, **kwargs):
        self.url = url

    def locator(self, selector):
        if selector in self._locators:
            return self._locators[selector]
        return FakeLocator(visible=False)

    def content(self):
        return self._content

    def evaluate(self, script, *args):
        pass


class InstagramHandlerTests(unittest.TestCase):
    @patch("src.handlers.platforms.instagram_handler.time.sleep", return_value=None)
    def test_working_dom_flow_types_credentials_and_accepts_onetap(self, _sleep):
        page = FakePage()
        account = Account("instagram_user", "instagram_password", "instagram")

        result = InstagramHandler().login(page, account)

        self.assertTrue(result)
        self.assertEqual(page.username.value, "instagram_user")
        self.assertEqual(page.password.value, "instagram_password")
        self.assertIn("accounts/onetap", page.url)


if __name__ == "__main__":
    unittest.main()
