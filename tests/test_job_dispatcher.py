import tempfile
import time
import unittest
from pathlib import Path

from src.core.executor import ExecutionSummary
from src.domains.execution_result import ExecutionResult, ResultCode
from src.domains.platform import Platform
from src.services.credential_cipher import CredentialCipher
from src.services.csv_account_parser import ParsedAccount
from src.services.job_dispatcher import JobDispatcher
from src.services.job_store import JobStore


class SuccessfulExecutor:
    def __init__(self, tasks, observers):
        self.tasks = tasks
        self.observers = observers

    def run(self):
        for observer in self.observers:
            observer.on_started(len(self.tasks))
        results = []
        for index, task in enumerate(self.tasks, 1):
            result = ExecutionResult(task, ResultCode.SUCCESS)
            results.append(result)
            for observer in self.observers:
                observer.on_result(result, index, len(self.tasks))
        summary = ExecutionSummary(results, 0.01)
        for observer in self.observers:
            observer.on_completed(summary)
        return summary


class DispatcherTests(unittest.TestCase):
    def test_dispatches_job_outside_caller_and_records_progress(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = JobStore(str(root / "test.db"), CredentialCipher(key_path=root / ".key"))
            batch = store.create_batch(
                Platform.TWITTER,
                "Test batch",
                "accounts.csv",
                [ParsedAccount("alice", "secret"), ParsedAccount("bob", "secret")],
            )
            job = store.create_job(
                batch, "like", "https://x.com/example/status/123", {}
            )
            dispatcher = JobDispatcher(
                store,
                executor_factory=lambda tasks, observers: SuccessfulExecutor(tasks, observers),
                poll_interval=0.01,
            )
            dispatcher.start()
            dispatcher.notify()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                current = store.get_job(job.id)
                if current.status == "completed":
                    break
                time.sleep(0.01)
            dispatcher.stop()

            current = store.get_job(job.id)
            self.assertEqual(current.status, "completed")
            self.assertEqual(current.completed, 2)
            self.assertEqual(current.succeeded, 2)
            self.assertEqual(len(store.list_results(job.id)), 2)


if __name__ == "__main__":
    unittest.main()
