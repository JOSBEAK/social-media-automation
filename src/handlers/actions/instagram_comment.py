# src/handlers/actions/instagram_comment.py
from src.interfaces.i_action_handler import IActionHandler
from src.domains.platform import Platform
from src.domains.action_type import ActionType
from src.domains.task import Task
from src.services.comment_manager import CommentManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random

class InstagramCommentHandler(IActionHandler):
    
    def __init__(self):
        self.comment_manager = CommentManager()

    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    @property
    def action_type(self) -> ActionType:
        return ActionType.COMMENT

    def execute(self, driver, task: Task) -> bool:
        try:
            driver.get(task.target_url)
            time.sleep(random.uniform(2, 4))
            
            comment_text = task.params.get("comment_text") if task.params else None
            if not comment_text:
                comment_text = self.comment_manager.generate_comment()
            
            input_box = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, '//textarea[@placeholder="Add a comment…"]'))
            )
            input_box.click()
            for char in comment_text:
                input_box.send_keys(char)
                time.sleep(random.uniform(0.05, 0.1))
            
            post_btn = driver.find_element(By.XPATH, '//button[contains(text(), "Post")]')
            post_btn.click()
            time.sleep(2)
            
            print(f"[Instagram] ✅ Commented: '{comment_text[:30]}...'")
            return True
        except Exception as e:
            print(f"[Instagram] Comment error: {str(e)[:100]}")
            return False
