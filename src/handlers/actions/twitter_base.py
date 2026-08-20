from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class TwitterActionMixin:
    timeout = 15

    def _wait_for_test_id(self, driver, *test_ids: str):
        selector = ", ".join(f'[data-testid="{test_id}"]' for test_id in test_ids)
        return WebDriverWait(driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )

    def _click_test_id(self, driver, test_id: str):
        element = WebDriverWait(driver, self.timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, f'[data-testid="{test_id}"]'))
        )
        driver.execute_script("arguments[0].click();", element)
        return element

    def _open_post(self, driver, url: str):
        driver.get(url)
        return WebDriverWait(driver, self.timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
        )

    def _post_control(self, article, *test_ids: str):
        selector = ", ".join(f'[data-testid="{test_id}"]' for test_id in test_ids)
        return WebDriverWait(article.parent, self.timeout).until(
            lambda _driver: next(iter(article.find_elements(By.CSS_SELECTOR, selector)), False)
        )
