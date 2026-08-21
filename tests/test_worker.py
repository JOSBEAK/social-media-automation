import unittest

from src.core.registry import Registry
from src.core.worker import Worker
from src.domains.action_type import ActionType
from src.domains.action_result import ActionResult
from src.domains.execution_result import ResultCode
from src.domains.platform import Platform
from src.domains.task import Task
from src.models.account import Account


class FakePlatform:
    platform = Platform.TWITTER

    def __init__(self, login_results):
        self.login_results = iter(login_results)
        self.calls = 0

    def login(self, driver, account):
        self.calls += 1
        return next(self.login_results)


class FakeAction:
    platform = Platform.TWITTER
    action_type = ActionType.LIKE

    def __init__(self, result=True):
        self.result = result
        self.calls = 0

    def execute(self, driver, task):
        self.calls += 1
        return self.result


class FakeDriver:
    def __init__(self):
        self.quit_called = False

    def quit(self):
        self.quit_called = True


class FakeBrowserFactory:
    drivers = []

    @classmethod
    def create_driver(cls, proxy=None):
        driver = FakeDriver()
        cls.drivers.append(driver)
        return driver


class FakeProxyManager:
    def get_next(self):
        return None


class RetrySettings:
    MAX_RETRIES = 1
    RETRY_DELAY = 0


def make_task():
    return Task(
        Account("user", "secret", "twitter"),
        Platform.TWITTER,
        ActionType.LIKE,
        "https://x.com/user/status/123",
    )


class WorkerTests(unittest.TestCase):
    def setUp(self):
        FakeBrowserFactory.drivers = []

    def make_worker(self, platform, action):
        registry = Registry()
        registry.register_platform(platform)
        registry.register_action(action)
        return Worker(
            FakeProxyManager(),
            registry,
            browser_factory=FakeBrowserFactory,
            settings=RetrySettings,
        )

    def test_retries_login_and_closes_every_driver(self):
        platform = FakePlatform([False, True])
        action = FakeAction(True)
        result = self.make_worker(platform, action).execute(make_task())

        self.assertEqual(result.code, ResultCode.SUCCESS)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(platform.calls, 2)
        self.assertTrue(all(driver.quit_called for driver in FakeBrowserFactory.drivers))

    def test_does_not_blindly_retry_failed_write(self):
        platform = FakePlatform([True])
        action = FakeAction(False)
        result = self.make_worker(platform, action).execute(make_task())

        self.assertEqual(result.code, ResultCode.ACTION_FAILED)
        self.assertEqual(action.calls, 1)
        self.assertEqual(len(FakeBrowserFactory.drivers), 1)

    def test_preserves_structured_action_failure_reason(self):
        platform = FakePlatform([True])
        action = FakeAction(ActionResult(False, "session cookie missing"))
        result = self.make_worker(platform, action).execute(make_task())

        self.assertEqual(result.code, ResultCode.ACTION_FAILED)
        self.assertEqual(result.error, "session cookie missing")


if __name__ == "__main__":
    unittest.main()
