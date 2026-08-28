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

    def execute(self, page, task) -> bool:
        try:
            article = self._open_post(page, task.target_url)
            button = self._post_control(article, "retweet", "unretweet")
            if button.get_attribute("data-testid") == "unretweet":
                return True
            button.click(force=True)
            self._click_test_id(page, "retweetConfirm")
            article.locator('[data-testid="unretweet"]').wait_for(
                state="visible", timeout=self.timeout
            )
            print(f"[Twitter] ✅ Reposted {task.target_url}")
            return True
        except Exception as exc:
            print(f"[Twitter] Repost error: {str(exc)[:160]}")
            return False
