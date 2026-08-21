# src/handlers/actions/instagram_like.py
from src.interfaces.i_action_handler import IActionHandler
from src.domains.platform import Platform
from src.domains.action_type import ActionType
from src.domains.task import Task
from src.domains.action_result import ActionResult
from src.handlers.actions.instagram_base import InstagramActionMixin
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
import time
import random

class InstagramLikeHandler(InstagramActionMixin, IActionHandler):
    LIKE_SELECTORS = (
        '//div[@role="button"]//svg[@aria-label="Like"]/ancestor::div[@role="button"]',
        '//svg[@aria-label="Like"]/ancestor::div[@role="button"]',
        '//button[@aria-label="Like"]',
        '//div[@role="button" and .//svg[@aria-label="Like"]]',
        '//svg[@aria-label="Like"]/ancestor::button',
        '//div[contains(@class, "wpO6b")]',
    )
    
    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    @property
    def action_type(self) -> ActionType:
        return ActionType.LIKE

    def execute(self, driver, task: Task) -> ActionResult:
        try:
            session_failure = self.require_session(driver)
            if session_failure is not None:
                return session_failure
            driver.get(task.target_url)
            time.sleep(random.uniform(2, 3))
            session_failure = self.require_session(driver)
            if session_failure is not None:
                return session_failure

            if driver.find_elements(By.XPATH, "//*[local-name()='svg'][@aria-label='Unlike']"):
                print(f"[Instagram] Already liked {task.target_url}")
                return ActionResult(True)
            
            try:
                like_svg = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//*[local-name()='svg'][@aria-label='Like']")
                    )
                )
                like_btn = like_svg.find_element(
                    By.XPATH, "./ancestor::div[@role='button'] | ./ancestor::button"
                )
                driver.execute_script("arguments[0].click();", like_btn)
                return self._confirmed_result(driver, task, "SVG parent")
            except TimeoutException:
                pass

            for selector in self.LIKE_SELECTORS:
                try:
                    like_btn = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    like_btn.click()
                    return self._confirmed_result(driver, task, selector)
                except (TimeoutException, ElementClickInterceptedException):
                    continue

            clicked = driver.execute_script(
                """
                const element = document.querySelector('[aria-label="Like"]');
                if (element) { element.click(); return true; }
                return false;
                """
            )
            if not clicked:
                print("[Instagram] Like button not found")
                return ActionResult(False, "Instagram like button was not found on the target post")

            return self._confirmed_result(driver, task, "JavaScript fallback")
        except Exception as e:
            print(f"[Instagram] Like error: {str(e)[:100]}")
            return ActionResult(False, f"Instagram like error: {type(e).__name__}: {e}")

    @staticmethod
    def _confirmed_result(driver, task: Task, method: str) -> ActionResult:
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[local-name()='svg'][@aria-label='Unlike']")
                )
            )
            print(f"[Instagram] ✅ Liked {task.target_url} via {method}")
            return ActionResult(True)
        except TimeoutException:
            return ActionResult(
                False,
                "Instagram like click was sent but the post never changed to the Unlike state",
            )
