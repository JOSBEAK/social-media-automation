import unittest
from unittest.mock import patch

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By

from src.handlers.platforms.instagram_handler import InstagramHandler
from src.models.account import Account


class FakeElement:
    def __init__(self, on_click=None):
        self.value = ""
        self.on_click = on_click

    def click(self):
        if self.on_click:
            self.on_click()

    def clear(self):
        self.value = ""

    def send_keys(self, value):
        self.value += value

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True


class FakeDriver:
    def __init__(self):
        self.current_url = InstagramHandler.LOGIN_URL
        self.page_source = ""
        self.username = FakeElement()
        self.password = FakeElement()
        self.login_button = FakeElement(self._login)
        self.cookies = {}
        self.elements = {
            (By.NAME, "username"): self.username,
            (By.NAME, "password"): self.password,
            # Exercise the same submit-button fallback used by the working project.
            (By.XPATH, '//button[@type="submit"]'): self.login_button,
        }

    def _login(self):
        self.current_url = "https://www.instagram.com/accounts/onetap/"
        self.cookies["sessionid"] = {"name": "sessionid", "value": "test-session"}

    def get(self, url):
        self.current_url = url

    def find_element(self, by, selector):
        try:
            return self.elements[(by, selector)]
        except KeyError as exc:
            raise NoSuchElementException() from exc

    def get_cookie(self, name):
        return self.cookies.get(name)

    def execute_script(self, script, element=None):
        if element:
            element.click()


class ImmediateWait:
    def __init__(self, driver, timeout):
        self.driver = driver

    def until(self, condition):
        try:
            result = condition(self.driver)
        except NoSuchElementException as exc:
            raise TimeoutException() from exc
        if not result:
            raise TimeoutException()
        return result


class InstagramHandlerTests(unittest.TestCase):
    @patch("src.handlers.platforms.instagram_handler.WebDriverWait", ImmediateWait)
    @patch("src.handlers.platforms.instagram_handler.time.sleep", return_value=None)
    def test_working_dom_flow_types_credentials_and_accepts_onetap(self, _sleep):
        driver = FakeDriver()
        account = Account("instagram_user", "instagram_password", "instagram")

        result = InstagramHandler().login(driver, account)

        self.assertTrue(result)
        self.assertEqual(driver.username.value, "instagram_user")
        self.assertEqual(driver.password.value, "instagram_password")
        self.assertIn("accounts/onetap", driver.current_url)


if __name__ == "__main__":
    unittest.main()
