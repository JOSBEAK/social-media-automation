# src/handlers/actions/instagram_comment.py
import platform
import random
import time

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from src.domains.action_result import ActionResult
from src.domains.action_type import ActionType
from src.domains.platform import Platform
from src.domains.task import Task
from src.handlers.actions.instagram_base import InstagramActionMixin
from src.interfaces.i_action_handler import IActionHandler
from src.services.comment_manager import CommentManager


class InstagramCommentHandler(InstagramActionMixin, IActionHandler):
    """Post an Instagram comment using stable accessibility attributes."""

    # Instagram's generated x... class names change frequently. These locators use
    # the accessible DOM attributes present in the supplied post dialog instead.
    COMMENT_BUTTON_SELECTORS = (
        (
            By.XPATH,
            "//*[local-name()='svg' and @aria-label='Comment']"
            "/ancestor::*[@role='button'][1]",
        ),
        (By.CSS_SELECTOR, "button[aria-label='Comment']"),
        (By.CSS_SELECTOR, "[role='button'][aria-label='Comment']"),
    )
    COMMENT_EDITOR_SELECTORS = (
        (
            By.CSS_SELECTOR,
            "div[role='textbox'][contenteditable='true'][aria-label='Add a comment…']",
        ),
        (
            By.CSS_SELECTOR,
            "div[role='textbox'][contenteditable='true'][aria-placeholder='Add a comment…']",
        ),
        (
            By.CSS_SELECTOR,
            "div[role='textbox'][contenteditable='true'][aria-label='Add a comment...']",
        ),
        (
            By.CSS_SELECTOR,
            "div[data-lexical-editor='true'][contenteditable='true']",
        ),
    )
    POST_BUTTON_SELECTORS = (
        (
            By.XPATH,
            "//*[@role='dialog']//*[@role='button' and normalize-space(.)='Post']",
        ),
        (By.XPATH, "//*[@role='button' and normalize-space(.)='Post']"),
        (By.XPATH, "//button[normalize-space(.)='Post']"),
    )

    def __init__(self):
        self.comment_manager = CommentManager()

    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    @property
    def action_type(self) -> ActionType:
        return ActionType.COMMENT

    def execute(self, driver, task: Task) -> ActionResult:
        try:
            session_failure = self.require_session(driver)
            if session_failure is not None:
                return session_failure

            driver.get(task.target_url)
            time.sleep(random.uniform(2, 4))

            session_failure = self.require_session(driver)
            if session_failure is not None:
                return session_failure

            comment_text = task.params.get("comment_text") if task.params else None
            if not comment_text:
                comment_text = self.comment_manager.generate_comment()
            comment_text = str(comment_text).strip()
            if not comment_text:
                return ActionResult(False, "Instagram comment text was empty")

            # Some post layouts expose the editor immediately. In others, the
            # supplied Comment SVG/button must be clicked to open the dialog.
            editor = self._optional_element(
                driver, self.COMMENT_EDITOR_SELECTORS, timeout=1.5
            )
            if editor is None:
                comment_button = self._optional_element(
                    driver,
                    self.COMMENT_BUTTON_SELECTORS,
                    timeout=5,
                    clickable=True,
                )
                if comment_button is None:
                    return ActionResult(
                        False,
                        "Instagram Comment button was not found on the target post",
                    )
                self._click(driver, comment_button)

                editor = self._optional_element(
                    driver, self.COMMENT_EDITOR_SELECTORS, timeout=8
                )
                if editor is None:
                    return ActionResult(
                        False,
                        "Instagram comment dialog opened, but the Add a comment… "
                        "textbox was not found",
                    )

            self._replace_editor_text(editor, comment_text)

            post_button = self._optional_element(
                driver, self.POST_BUTTON_SELECTORS, timeout=5, clickable=True
            )
            if post_button is None:
                return ActionResult(
                    False,
                    "Instagram comment was entered, but the Post button was not found",
                )

            self._click(driver, post_button)
            if not self._wait_until_submitted(driver, editor, timeout=8):
                return ActionResult(
                    False,
                    "Instagram Post was clicked, but submission was not confirmed "
                    "because the comment textbox did not clear",
                )

            session_failure = self.require_session(driver)
            if session_failure is not None:
                return session_failure

            print(f"[Instagram] ✅ Commented: '{comment_text[:30]}...'", flush=True)
            return ActionResult(True)
        except Exception as exc:
            print(f"[Instagram] Comment error: {str(exc)[:100]}", flush=True)
            return ActionResult(
                False,
                f"Instagram comment error: {type(exc).__name__}: {exc}",
            )

    @staticmethod
    def _optional_element(driver, selectors, timeout: float, clickable: bool = False):
        def first_matching_element(current_driver):
            for by, selector in selectors:
                for element in current_driver.find_elements(by, selector):
                    try:
                        if not element.is_displayed():
                            continue
                        if clickable and not element.is_enabled():
                            continue
                        return element
                    except Exception:
                        continue
            return False

        try:
            return WebDriverWait(driver, timeout).until(first_matching_element)
        except TimeoutException:
            return None

    @staticmethod
    def _click(driver, element) -> None:
        try:
            element.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", element)

    @staticmethod
    def _replace_editor_text(editor, comment_text: str) -> None:
        editor.click()
        modifier = Keys.COMMAND if platform.system() == "Darwin" else Keys.CONTROL
        editor.send_keys(modifier, "a")
        editor.send_keys(Keys.BACKSPACE)
        for char in comment_text:
            editor.send_keys(char)
            time.sleep(random.uniform(0.04, 0.09))

    @classmethod
    def _wait_until_submitted(cls, driver, editor, timeout: float) -> bool:
        def editor_was_cleared(_driver):
            try:
                return cls._editor_text(editor).strip() == ""
            except StaleElementReferenceException:
                # Lexical can replace the editor node after a successful submit.
                return True

        try:
            WebDriverWait(driver, timeout).until(editor_was_cleared)
            return True
        except TimeoutException:
            return False

    @staticmethod
    def _editor_text(editor) -> str:
        return editor.get_attribute("textContent") or editor.text or ""
