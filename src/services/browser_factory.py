# src/services/browser_factory.py
import os
import stat
import threading
from pathlib import Path
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
            if not Path(configured_path).is_file():
                raise FileNotFoundError(f"CHROMEDRIVER_PATH is not a file: {configured_path}")
            return configured_path

        if cls._driver_path is None:
            with cls._install_lock:
                if cls._driver_path is None:
                    cached_path = cls._find_cached_driver()
                    if cached_path:
                        cls._driver_path = cached_path
                    else:
                        installed_path = ChromeDriverManager().install()
                        cls._driver_path = cls._resolve_managed_driver_path(installed_path)
        return cls._driver_path

    @classmethod
    def _find_cached_driver(cls, cache_root: Path | None = None) -> str | None:
        root = cache_root or (Path.home() / ".wdm" / "drivers" / "chromedriver")
        if not root.exists():
            return None
        driver_names = {"chromedriver", "chromedriver.exe"}
        candidates = [
            path
            for path in root.rglob("chromedriver*")
            if path.is_file() and path.name.lower() in driver_names
        ]
        if not candidates:
            return None
        newest = max(candidates, key=lambda path: path.stat().st_mtime)
        return cls._resolve_managed_driver_path(str(newest))

    @staticmethod
    def _resolve_managed_driver_path(installed_path: str) -> str:
        """Work around webdriver-manager returning a notice/license file."""
        installed = Path(installed_path)
        driver_names = {"chromedriver", "chromedriver.exe"}
        if installed.is_file() and installed.name.lower() in driver_names:
            candidate = installed
        else:
            candidates = sorted(
                (
                    path
                    for path in installed.parent.rglob("chromedriver*")
                    if path.is_file() and path.name.lower() in driver_names
                ),
                key=lambda path: (len(path.parts), str(path)),
            )
            if not candidates:
                raise FileNotFoundError(
                    f"webdriver-manager did not provide a ChromeDriver binary near {installed_path}"
                )
            candidate = candidates[0]

        if os.name != "nt" and not os.access(candidate, os.X_OK):
            candidate.chmod(candidate.stat().st_mode | stat.S_IXUSR)
        return str(candidate)

    @classmethod
    def create_driver(cls, proxy: str = None, headless: Optional[bool] = None):
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option("detach", True)
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        if proxy:
            if "://" not in proxy:
                proxy = f"http://{proxy}"
            options.add_argument(f"--proxy-server={proxy}")
        if Settings.HEADLESS if headless is None else headless:
            options.add_argument("--headless=new")

        driver = webdriver.Chrome(service=Service(cls._get_driver_path()), options=options)
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        driver.implicitly_wait(Settings.IMPLICIT_WAIT)
        return driver
