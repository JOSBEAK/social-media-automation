# src/services/browser_factory.py
import os
import threading
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from src.config.settings import Settings

class BrowserFactory:
    _driver_path: Optional[str] = None
    _install_lock = threading.Lock()

    @classmethod
    def _get_driver_path(cls) -> str:
        configured_path = os.getenv("CHROMEDRIVER_PATH")
        if configured_path:
            return configured_path

        if cls._driver_path is None:
            with cls._install_lock:
                if cls._driver_path is None:
                    cls._driver_path = ChromeDriverManager().install()
        return cls._driver_path

    @classmethod
    def create_driver(cls, proxy: str = None, headless: Optional[bool] = None):
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        if proxy:
            options.add_argument(f"--proxy-server={proxy}")
        if Settings.HEADLESS if headless is None else headless:
            options.add_argument("--headless=new")

        driver = webdriver.Chrome(service=Service(cls._get_driver_path()), options=options)
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        driver.implicitly_wait(2)
        return driver
