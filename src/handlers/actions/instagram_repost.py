# src/handlers/actions/instagram_repost.py
from src.interfaces.i_action_handler import IActionHandler
from src.domains.platform import Platform
from src.domains.action_type import ActionType
from src.domains.task import Task
from src.domains.action_result import ActionResult
from src.handlers.actions.instagram_base import InstagramActionMixin
from playwright.sync_api import TimeoutError as PlaywrightTimeout
import time
import random

class InstagramRepostHandler(InstagramActionMixin, IActionHandler):
    
    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    @property
    def action_type(self) -> ActionType:
        return ActionType.REPOST

    def execute(self, page, task: Task) -> bool | ActionResult:
        try:
            session_failure = self.require_session(page)
            if session_failure:
                return session_failure
            page.goto(task.target_url, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 4))
            session_failure = self.require_session(page)
            if session_failure:
                return session_failure
            
            share_btn = page.locator('div[role="button"]:has(svg[aria-label="Share"])')
            share_btn.first.click(timeout=5000)
            time.sleep(1)
            
            repost_opt = page.locator('div[role="button"]:has-text("Repost")')
            repost_opt.first.click()
            time.sleep(2)
            
            print(f"[Instagram] ✅ Reposted {task.target_url}")
            return True
        except Exception as e:
            print(f"[Instagram] Repost error: {str(e)[:100]}")
            return ActionResult(False, f"Instagram repost error: {type(e).__name__}: {e}")
