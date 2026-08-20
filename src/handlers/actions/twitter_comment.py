from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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

    def execute(self, driver, task) -> bool:
        try:
            article = self._open_post(driver, task.target_url)
            comment = task.params.get("comment_text") or self.comment_manager.generate_comment()
            reply = self._post_control(article, "reply")
            driver.execute_script("arguments[0].click();", reply)
            editor = WebDriverWait(driver, self.timeout).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetTextarea_0"]'))
            )
            editor.send_keys(comment)
            self._click_test_id(driver, "tweetButton")
            WebDriverWait(driver, self.timeout).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, '[data-testid="tweetButton"]'))
            )
            print(f"[Twitter] ✅ Replied: '{comment[:30]}...' ")
            return True
        except Exception as exc:
            print(f"[Twitter] Reply error: {str(exc)[:160]}")
            return False
