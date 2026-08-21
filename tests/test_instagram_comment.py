import unittest
from unittest.mock import patch

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

from src.domains.action_type import ActionType
from src.domains.platform import Platform
from src.domains.task import Task
from src.handlers.actions.instagram_comment import InstagramCommentHandler
from src.models.account import Account


class ImmediateWait:
    def __init__(self, driver, timeout):
        self.driver = driver

    def until(self, condition):
        result = condition(self.driver)
        if not result:
            raise TimeoutException()
        return result


class FakeElement:
    def __init__(self, on_click=None):
        self.on_click = on_click
        self.content = ""
        self.select_all = False

    @property
    def text(self):
        return self.content

    def click(self):
        if self.on_click:
            self.on_click()

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def send_keys(self, *values):
        if len(values) == 2 and values[1] == "a":
            self.select_all = True
            return
        value = "".join(values)
        if value == Keys.BACKSPACE:
            self.content = "" if self.select_all else self.content[:-1]
            self.select_all = False
            return
        self.content += value

    def get_attribute(self, name):
        return self.content if name == "textContent" else None


class SuppliedInstagramDomDriver:
    def __init__(self):
        self.dialog_open = False
        self.current_url = ""
        self.editor = FakeElement()
        self.comment_button = FakeElement(self._open_dialog)
        self.post_button = FakeElement(self._submit_comment)

    def _open_dialog(self):
        self.dialog_open = True

    def _submit_comment(self):
        self.editor.content = ""

    def get(self, url):
        self.current_url = url

    def get_cookie(self, name):
        if name == "sessionid":
            return {"name": "sessionid", "value": "authenticated-session"}
        return None

    def find_elements(self, by, selector):
        if "aria-label='Comment'" in selector:
            return [self.comment_button]
        if "Add a comment" in selector or "data-lexical-editor" in selector:
            return [self.editor] if self.dialog_open else []
        if "normalize-space(.)='Post'" in selector:
            return [self.post_button] if self.dialog_open else []
        return []

    def execute_script(self, script, element):
        element.click()


class InstagramCommentTests(unittest.TestCase):
    @patch("src.handlers.actions.instagram_comment.WebDriverWait", ImmediateWait)
    @patch("src.handlers.actions.instagram_comment.time.sleep", return_value=None)
    def test_supplied_accessible_dom_posts_and_confirms_comment(self, _sleep):
        driver = SuppliedInstagramDomDriver()
        task = Task(
            account=Account("user", "password", "instagram"),
            platform=Platform.INSTAGRAM,
            action=ActionType.COMMENT,
            target_url="https://www.instagram.com/p/example/",
            params={"comment_text": "Great post"},
        )

        result = InstagramCommentHandler().execute(driver, task)

        self.assertTrue(result)
        self.assertTrue(driver.dialog_open)
        self.assertEqual(driver.editor.content, "")

    @patch("src.handlers.actions.instagram_comment.time.sleep", return_value=None)
    def test_missing_session_stops_before_navigation(self, _sleep):
        driver = SuppliedInstagramDomDriver()
        driver.get_cookie = lambda name: None
        task = Task(
            account=Account("user", "password", "instagram"),
            platform=Platform.INSTAGRAM,
            action=ActionType.COMMENT,
            target_url="https://www.instagram.com/p/example/",
            params={"comment_text": "Great post"},
        )

        result = InstagramCommentHandler().execute(driver, task)

        self.assertFalse(result)
        self.assertIn("no sessionid cookie", result.error)
        self.assertEqual(driver.current_url, "")


if __name__ == "__main__":
    unittest.main()
