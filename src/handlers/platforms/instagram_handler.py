# src/handlers/platforms/instagram_handler.py
from src.interfaces.i_platform_handler import IPlatformHandler
from src.domains.platform import Platform
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random

class InstagramHandler(IPlatformHandler):
    
    @property
    def platform(self) -> Platform:
        return Platform.INSTAGRAM

    def get_post_url(self, identifier: str) -> str:
        return f"https://www.instagram.com/p/{identifier}/"

    def login(self, driver, account) -> bool:
        try:
            driver.get("https://www.instagram.com/accounts/login/")
            time.sleep(random.uniform(2, 4))
            
            user_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            user_field.send_keys(account.username)
            
            pass_field = driver.find_element(By.NAME, "password")
            pass_field.send_keys(account.password)
            
            login_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//div[@aria-label="Log in" and @role="button"]'))
            )
            login_btn.click()
            time.sleep(5)
            
            if "login" not in driver.current_url.lower():
                print("[Instagram] ✅ Login success")
                return True
            return False
        except Exception as e:
            print(f"[Instagram] Login error: {str(e)[:100]}")
            return False
