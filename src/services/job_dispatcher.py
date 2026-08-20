import threading
from typing import Callable

from src.config.settings import Settings
from src.core.executor import Executor
from src.domains.action_type import ActionType
from src.domains.platform import Platform
from src.domains.task import Task
from src.services.job_store import JobRecord, JobStore


class JobProgressObserver:
    def __init__(self, store: JobStore, job_id: str) -> None:
        self.store = store
        self.job_id = job_id

    def on_started(self, total: int) -> None:
        return None

    def on_result(self, result, completed: int, total: int) -> None:
        self.store.record_result(self.job_id, result)

    def on_completed(self, summary) -> None:
        return None


def default_executor_factory(tasks, observers):
    return Executor(tasks, observers=observers)


class JobDispatcher:
    """Runs blocking browser executors outside the API/event-loop threads."""

    def __init__(
        self,
        store: JobStore,
        executor_factory: Callable = default_executor_factory,
        worker_count: int = Settings.JOB_WORKERS,
        poll_interval: float = Settings.JOB_POLL_INTERVAL,
    ) -> None:
        self.store = store
        self.executor_factory = executor_factory
        self.worker_count = worker_count
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        if self._threads:
            return
        self.store.fail_interrupted_jobs()
        self._stop_event.clear()
        for index in range(self.worker_count):
            thread = threading.Thread(
                target=self._consume,
                name=f"job-dispatcher-{index + 1}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)

    def notify(self) -> None:
        self._wake_event.set()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop_event.set()
        self._wake_event.set()
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads.clear()

    def _consume(self) -> None:
        while not self._stop_event.is_set():
            job = self.store.claim_next_job()
            if job is None:
                self._wake_event.wait(self.poll_interval)
                self._wake_event.clear()
                continue
            self._execute(job)

    def _execute(self, job: JobRecord) -> None:
        try:
            accounts = self.store.load_accounts(job.batch_id)
            platform = Platform.parse(job.platform)
            action = ActionType.parse(job.action)
            tasks = [
                Task(
                    account=account,
                    platform=platform,
                    action=action,
                    target_url=job.target_url,
                    params=job.params.copy(),
                )
                for account in accounts
            ]
            observer = JobProgressObserver(self.store, job.id)
            self.executor_factory(tasks, (observer,)).run()
            self.store.complete_job(job.id)
        except Exception as exc:
            self.store.fail_job(job.id, f"{type(exc).__name__}: {exc}")
