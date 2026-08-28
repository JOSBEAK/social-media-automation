# src/services/browser_factory.py
import threading
from typing import Optional

from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page

from src.config.settings import Settings


class BrowserFactory:
    """Manages a shared Playwright instance and Chromium browser.

    Each call to ``create_context`` returns an isolated ``BrowserContext`` with
    its own cookies, storage, and a single ``Page``.  Workers must close the
    context when finished (the ``Worker`` does this in its ``finally`` block).

    The first call lazily starts the Playwright process and launches the shared
    browser.  A threading lock prevents races when multiple worker threads
    start simultaneously.
    """

    _playwright: Optional[Playwright] = None
    _browser: Optional[Browser] = None
    _lock = threading.Lock()

    @classmethod
    def _ensure_browser(cls, headless: Optional[bool] = None) -> Browser:
        if cls._browser is None or not cls._browser.is_connected():
            with cls._lock:
                if cls._browser is None or not cls._browser.is_connected():
                    cls._playwright = sync_playwright().start()
                    use_headless = Settings.HEADLESS if headless is None else headless
                    cls._browser = cls._playwright.chromium.launch(
                        headless=use_headless,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                        ],
                    )
        return cls._browser

    @classmethod
    def create_context(cls, proxy: str = None, headless: Optional[bool] = None) -> tuple[BrowserContext, Page]:
        """Create an isolated BrowserContext and a Page within it.

        Returns ``(context, page)`` so the caller can close the context when
        done and still have direct page access for navigation.
        """
        browser = cls._ensure_browser(headless)

        context_kwargs = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        }

        if proxy:
            if "://" not in proxy:
                proxy = f"http://{proxy}"
            context_kwargs["proxy"] = {"server": proxy}

        context = browser.new_context(**context_kwargs)

        # Mask the navigator.webdriver flag the same way the old Selenium code did.
        context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = context.new_page()
        page.set_default_timeout(Settings.DEFAULT_TIMEOUT * 1000)

        return context, page

    # Legacy alias kept so that the Worker can be swapped without touching
    # the Executor or its tests.  The Worker now expects a ``(context, page)``
    # tuple instead of a bare driver.
    create_driver = create_context

    @classmethod
    def shutdown(cls) -> None:
        """Close the shared browser and stop Playwright."""
        with cls._lock:
            if cls._browser:
                try:
                    cls._browser.close()
                except Exception:
                    pass
                cls._browser = None
            if cls._playwright:
                try:
                    cls._playwright.stop()
                except Exception:
                    pass
                cls._playwright = None
