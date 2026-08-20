# src/handlers/actions/instagram_repost.py
from src.interfaces.i_action_handler import IActionHandler
from src.domains.platform import Platform
from src.domains.action_type import ActionType
from src.domains.task import Task
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random

class InstagramRepostHandler(IActionHandler):
    
    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    @property
    def action_type(self) -> ActionType:
        return ActionType.REPOST

    def execute(self, driver, task: Task) -> bool:
        try:
            driver.get(task.target_url)
            time.sleep(random.uniform(2, 4))
            
            share_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//svg[@aria-label="Share"]/ancestor::div[@role="button"]'))
            )
            share_btn.click()
            time.sleep(1)
            
            repost_opt = driver.find_element(By.XPATH, '//span[contains(text(), "Repost")]/ancestor::div[@role="button"]')
            repost_opt.click()
            time.sleep(2)
            
            print(f"[Instagram] ✅ Reposted {task.target_url}")
            return True
        except Exception as e:
            print(f"[Instagram] Repost error: {str(e)[:100]}")
            return False
