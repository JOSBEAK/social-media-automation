# src/handlers/actions/instagram_like.py
from src.interfaces.i_action_handler import IActionHandler
from src.domains.platform import Platform
from src.domains.action_type import ActionType
from src.domains.task import Task
from src.domains.action_result import ActionResult
from src.handlers.actions.instagram_base import InstagramActionMixin
from playwright.sync_api import TimeoutError as PlaywrightTimeout
import time
import random

class InstagramLikeHandler(InstagramActionMixin, IActionHandler):
    LIKE_SELECTORS = (
        'div[role="button"]:has(svg[aria-label="Like"])',
        'button[aria-label="Like"]',
        'button:has(svg[aria-label="Like"])',
    )
    
    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    @property
    def action_type(self) -> ActionType:
        return ActionType.LIKE

    def execute(self, page, task: Task) -> ActionResult:
        try:
            session_failure = self.require_session(page)
            if session_failure:
                return session_failure
            page.goto(task.target_url, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 3))
            session_failure = self.require_session(page)
            if session_failure:
                return session_failure

            # Check if already liked
            unlike = page.locator('svg[aria-label="Unlike"]')
            if unlike.count() > 0:
                print(f"[Instagram] Already liked {task.target_url}")
                return ActionResult(True)
            
            # Primary approach: find the Like SVG and click its button ancestor
            try:
                like_svg = page.locator('svg[aria-label="Like"]').first
                like_svg.wait_for(state="visible", timeout=3000)
                # Click the parent button/div
                like_btn = like_svg.locator("xpath=ancestor::div[@role='button'] | ancestor::button").first
                like_btn.click(force=True)
                return self._confirmed_result(page, task, "SVG parent")
            except PlaywrightTimeout:
                pass

            # Fallback selectors
            for selector in self.LIKE_SELECTORS:
                try:
                    locator = page.locator(selector).first
                    locator.click(timeout=2000)
                    return self._confirmed_result(page, task, selector)
                except (PlaywrightTimeout, Exception):
                    continue

            # JavaScript fallback
            clicked = page.evaluate("""
                const element = document.querySelector('[aria-label="Like"]');
                if (element) { element.click(); return true; }
                return false;
            """)
            if not clicked:
                print("[Instagram] Like button not found")
                return ActionResult(False, "Instagram like button was not found on the target post")

            return self._confirmed_result(page, task, "JavaScript fallback")
        except Exception as e:
            print(f"[Instagram] Like error: {str(e)[:100]}")
            return ActionResult(False, f"Instagram like error: {type(e).__name__}: {e}")

    @staticmethod
    def _confirmed_result(page, task: Task, method: str) -> ActionResult:
        try:
            page.locator('svg[aria-label="Unlike"]').first.wait_for(
                state="visible", timeout=5000
            )
            print(f"[Instagram] ✅ Liked {task.target_url} via {method}")
            return ActionResult(True)
        except PlaywrightTimeout:
            return ActionResult(
                False,
                "Instagram like click was sent but the post never changed to the Unlike state",
            )
