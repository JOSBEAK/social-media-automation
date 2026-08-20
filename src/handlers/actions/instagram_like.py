# src/handlers/actions/instagram_like.py
from src.interfaces.i_action_handler import IActionHandler
from src.domains.platform import Platform
from src.domains.action_type import ActionType
from src.domains.task import Task
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random

class InstagramLikeHandler(IActionHandler):
    
    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    @property
    def action_type(self) -> ActionType:
        return ActionType.LIKE

    def execute(self, driver, task: Task) -> bool:
        try:
            driver.get(task.target_url)
            time.sleep(random.uniform(2, 4))
            
            like_svg = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//*[local-name()='svg'][@aria-label='Like']"))
            )
            like_btn = like_svg.find_element(By.XPATH, "./ancestor::div[@role='button'] | ./ancestor::button")
            driver.execute_script("arguments[0].click();", like_btn)
            
            print(f"[Instagram] ✅ Liked {task.target_url}")
            return True
        except Exception as e:
            print(f"[Instagram] Like error: {str(e)[:100]}")
            return False
