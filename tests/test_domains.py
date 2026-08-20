import unittest

from src.domains.action_type import ActionType
from src.domains.platform import Platform
from src.domains.task import Task
from src.models.account import Account


class DomainTests(unittest.TestCase):
    def test_aliases_are_canonicalized(self):
        self.assertIs(Platform.parse("X"), Platform.TWITTER)
        self.assertIs(ActionType.parse("retweet"), ActionType.REPOST)
        self.assertIs(ActionType.parse("reply"), ActionType.COMMENT)

    def test_task_rejects_cross_platform_url(self):
        task = Task(
            Account("user", "secret", "twitter"),
            Platform.TWITTER,
            ActionType.LIKE,
            "https://www.instagram.com/p/123/",
        )
        self.assertIn("host does not match", task.validation_error())

    def test_x_and_twitter_urls_are_valid(self):
        account = Account("user", "secret", "x")
        for url in (
            "https://x.com/user/status/123",
            "https://twitter.com/user/status/123",
        ):
            task = Task(account, "twitter", "like", url)
            self.assertIsNone(task.validation_error())


if __name__ == "__main__":
    unittest.main()
