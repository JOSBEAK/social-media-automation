class TwitterActionMixin:
    timeout = 15000  # milliseconds for Playwright

    def _wait_for_test_id(self, page, *test_ids: str):
        selector = ", ".join(f'[data-testid="{test_id}"]' for test_id in test_ids)
        locator = page.locator(selector).first
        locator.wait_for(state="visible", timeout=self.timeout)
        return locator

    def _click_test_id(self, page, test_id: str):
        locator = page.locator(f'[data-testid="{test_id}"]')
        locator.click(force=True, timeout=self.timeout)
        return locator

    def _open_post(self, page, url: str):
        page.goto(url, wait_until="domcontentloaded")
        article = page.locator('article[data-testid="tweet"]').first
        article.wait_for(state="visible", timeout=self.timeout)
        return article

    def _post_control(self, article, *test_ids: str):
        selector = ", ".join(f'[data-testid="{test_id}"]' for test_id in test_ids)
        locator = article.locator(selector).first
        locator.wait_for(state="visible", timeout=self.timeout)
        return locator
