# src/handlers/actions/instagram_comment.py
from src.interfaces.i_action_handler import IActionHandler
from src.domains.platform import Platform
from src.domains.action_type import ActionType
from src.domains.task import Task
from src.domains.action_result import ActionResult
from src.handlers.actions.instagram_base import InstagramActionMixin
from src.services.comment_manager import CommentManager
from playwright.sync_api import TimeoutError as PlaywrightTimeout
import time
import random

class InstagramCommentHandler(InstagramActionMixin, IActionHandler):
    
    def __init__(self):
        self.comment_manager = CommentManager()

    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    @property
    def action_type(self) -> ActionType:
        return ActionType.COMMENT

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
            
            comment_text = task.params.get("comment_text") if task.params else None
            if not comment_text:
                comment_text = self.comment_manager.generate_comment()
            
            input_box = page.locator('textarea[placeholder="Add a comment…"]')
            input_box.click(timeout=5000)
            for char in comment_text:
                input_box.press_sequentially(char, delay=random.uniform(50, 100))
            
            post_btn = page.locator('button:has-text("Post")')
            post_btn.click()
            time.sleep(2)
            
            print(f"[Instagram] ✅ Commented: '{comment_text[:30]}...'")
            return True
        except Exception as e:
            print(f"[Instagram] Comment error: {str(e)[:100]}")
            return ActionResult(False, f"Instagram comment error: {type(e).__name__}: {e}")
