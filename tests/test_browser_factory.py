import os
import tempfile
import unittest
from pathlib import Path

from src.services.browser_factory import BrowserFactory


class BrowserFactoryTests(unittest.TestCase):
    def test_resolves_real_driver_when_manager_returns_notice_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            notice = folder / "THIRD_PARTY_NOTICES.chromedriver"
            driver = folder / ("chromedriver.exe" if os.name == "nt" else "chromedriver")
            notice.write_text("not an executable driver", encoding="utf-8")
            driver.write_bytes(b"driver")

            resolved = BrowserFactory._resolve_managed_driver_path(str(notice))

            self.assertEqual(Path(resolved), driver)
            if os.name != "nt":
                self.assertTrue(os.access(driver, os.X_OK))

    def test_finds_cached_driver_without_network_lookup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "151" / "driver-package"
            folder.mkdir(parents=True)
            driver = folder / ("chromedriver.exe" if os.name == "nt" else "chromedriver")
            driver.write_bytes(b"driver")

            resolved = BrowserFactory._find_cached_driver(Path(temp_dir))

            self.assertEqual(Path(resolved), driver)


if __name__ == "__main__":
    unittest.main()
