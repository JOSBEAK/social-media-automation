import threading
import time
import unittest
from collections import defaultdict

from src.core.executor import Executor
from src.domains.action_type import ActionType
from src.domains.execution_result import ExecutionResult, ResultCode
from src.domains.platform import Platform
from src.domains.task import Task
from src.models.account import Account


class SchedulingSettings:
    MAX_WORKERS = 3

    @staticmethod
    def worker_limit(platform):
        return 1

    @staticmethod
    def get_cooldown():
        return 0


class NoopProxyManager:
    pass


class RecordingWorker:
    lock = threading.Lock()
    active_accounts = defaultdict(int)
    active_platforms = defaultdict(int)
    max_accounts = defaultdict(int)
    max_platforms = defaultdict(int)

    def __init__(self, proxy_manager, registry, settings):
        pass

    def execute(self, task):
        with self.lock:
            self.active_accounts[task.account_key] += 1
            self.active_platforms[task.platform] += 1
            self.max_accounts[task.account_key] = max(
                self.max_accounts[task.account_key], self.active_accounts[task.account_key]
            )
            self.max_platforms[task.platform] = max(
                self.max_platforms[task.platform], self.active_platforms[task.platform]
            )
        time.sleep(0.02)
        with self.lock:
            self.active_accounts[task.account_key] -= 1
            self.active_platforms[task.platform] -= 1
        return ExecutionResult(task, ResultCode.SUCCESS)


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        RecordingWorker.active_accounts.clear()
        RecordingWorker.active_platforms.clear()
        RecordingWorker.max_accounts.clear()
        RecordingWorker.max_platforms.clear()

    def test_enforces_account_and_platform_limits(self):
        instagram_account = Account("ig", "secret", "instagram")
        twitter_account = Account("tw", "secret", "twitter")
        tasks = [
            Task(instagram_account, "instagram", "like", "https://instagram.com/p/1/"),
            Task(instagram_account, "instagram", "repost", "https://instagram.com/p/2/"),
            Task(twitter_account, "twitter", "like", "https://x.com/tw/status/1"),
            Task(twitter_account, "twitter", "repost", "https://x.com/tw/status/2"),
        ]
        summary = Executor(
            tasks,
            registry=object(),
            proxy_manager=NoopProxyManager(),
            settings=SchedulingSettings,
            worker_factory=RecordingWorker,
        ).run()

        self.assertEqual(summary.succeeded, 4)
        self.assertTrue(all(value == 1 for value in RecordingWorker.max_accounts.values()))
        self.assertTrue(all(value == 1 for value in RecordingWorker.max_platforms.values()))


if __name__ == "__main__":
    unittest.main()
