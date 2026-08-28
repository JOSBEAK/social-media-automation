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


    def test_multithreaded_context_creation(self):
        """Verify contexts can be created and closed across multiple concurrent threads."""
        import concurrent.futures

        def worker_fn():
            context, page = BrowserFactory.create_context(headless=True)
            page.goto("about:blank")
            context.close()
            return True

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(worker_fn) for _ in range(3)]
            results = [f.result() for f in futures]
            self.assertTrue(all(results))

        BrowserFactory.shutdown()


if __name__ == "__main__":
    unittest.main()
