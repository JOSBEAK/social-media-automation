from selenium.webdriver.support.ui import WebDriverWait

from src.domains.action_type import ActionType
from src.domains.platform import Platform
from src.handlers.actions.twitter_base import TwitterActionMixin
from src.interfaces.i_action_handler import IActionHandler


class TwitterRepostHandler(TwitterActionMixin, IActionHandler):
    @property
    def platform(self) -> Platform:
        return Platform.TWITTER

    @property
    def action_type(self) -> ActionType:
        return ActionType.REPOST

    def execute(self, driver, task) -> bool:
        try:
            article = self._open_post(driver, task.target_url)
            button = self._post_control(article, "retweet", "unretweet")
            if button.get_attribute("data-testid") == "unretweet":
                return True
            driver.execute_script("arguments[0].click();", button)
            self._click_test_id(driver, "retweetConfirm")
            WebDriverWait(driver, self.timeout).until(
                lambda _driver: article.find_elements("css selector", '[data-testid="unretweet"]')
            )
            print(f"[Twitter] ✅ Reposted {task.target_url}")
            return True
        except Exception as exc:
            print(f"[Twitter] Repost error: {str(exc)[:160]}")
            return False
