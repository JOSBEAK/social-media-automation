import unittest

from src.services.browser_factory import BrowserFactory


class BrowserFactoryTests(unittest.TestCase):
    def test_browser_factory_has_create_context(self):
        """Verify the Playwright BrowserFactory exposes the expected API."""
        self.assertTrue(hasattr(BrowserFactory, "create_context"))
        self.assertTrue(hasattr(BrowserFactory, "create_driver"))  # legacy alias
        self.assertTrue(hasattr(BrowserFactory, "shutdown"))

    def test_create_context_alias_matches_create_context(self):
        self.assertEqual(
            BrowserFactory.create_driver.__func__,
            BrowserFactory.create_context.__func__,
        )


if __name__ == "__main__":
    unittest.main()
