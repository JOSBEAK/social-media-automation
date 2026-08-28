from src.domains.action_type import ActionType
from src.domains.platform import Platform
from src.handlers.actions.twitter_base import TwitterActionMixin
from src.interfaces.i_action_handler import IActionHandler
from src.services.comment_manager import CommentManager


class TwitterCommentHandler(TwitterActionMixin, IActionHandler):
    def __init__(self) -> None:
        self.comment_manager = CommentManager()

    @property
    def platform(self) -> Platform:
        return Platform.TWITTER

    @property
    def action_type(self) -> ActionType:
        return ActionType.COMMENT

    def execute(self, page, task) -> bool:
        try:
            article = self._open_post(page, task.target_url)
            comment = task.params.get("comment_text") or self.comment_manager.generate_comment()
            reply = self._post_control(article, "reply")
            reply.click(force=True)
            editor = page.locator('[data-testid="tweetTextarea_0"]')
            editor.wait_for(state="visible", timeout=self.timeout)
            editor.fill(comment)
            self._click_test_id(page, "tweetButton")
            page.locator('[data-testid="tweetButton"]').wait_for(
                state="hidden", timeout=self.timeout
            )
            print(f"[Twitter] ✅ Replied: '{comment[:30]}...' ")
            return True
        except Exception as exc:
            print(f"[Twitter] Reply error: {str(exc)[:160]}")
            return False
