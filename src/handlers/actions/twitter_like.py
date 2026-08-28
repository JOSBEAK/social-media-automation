from src.domains.action_type import ActionType
from src.domains.platform import Platform
from src.handlers.actions.twitter_base import TwitterActionMixin
from src.interfaces.i_action_handler import IActionHandler


class TwitterLikeHandler(TwitterActionMixin, IActionHandler):
    @property
    def platform(self) -> Platform:
        return Platform.TWITTER

    @property
    def action_type(self) -> ActionType:
        return ActionType.LIKE

    def execute(self, page, task) -> bool:
        try:
            article = self._open_post(page, task.target_url)
            button = self._post_control(article, "like", "unlike")
            if button.get_attribute("data-testid") == "unlike":
                return True
            button.click(force=True)
            article.locator('[data-testid="unlike"]').wait_for(
                state="visible", timeout=self.timeout
            )
            print(f"[Twitter] TASK_SUCCESS Liked {task.target_url}")
            return True
        except Exception as exc:
            print(f"[Twitter] Like error: {str(exc)[:160]}")
            return False
