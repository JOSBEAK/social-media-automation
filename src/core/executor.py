import time
from collections import defaultdict, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Callable, Deque, Dict, Iterable, List, Optional

from src.config.settings import Settings
from src.core.worker import Worker
from src.domains.execution_result import ExecutionResult, ResultCode
from src.domains.platform import Platform
from src.domains.task import Task
from src.services.proxy_manager import ProxyManager


@dataclass(frozen=True)
class ExecutionSummary:
    results: List[ExecutionResult]
    elapsed_seconds: float

    @property
    def succeeded(self) -> int:
        return sum(result.success for result in self.results)

    @property
    def failed(self) -> int:
        return len(self.results) - self.succeeded


class Executor:
    def __init__(
        self,
        tasks: Iterable[Task],
        registry=None,
        proxy_manager=None,
        settings=Settings,
        worker_factory: Callable = Worker,
        observers: Optional[Iterable] = None,
    ) -> None:
        self.tasks = list(tasks)
        if registry is None:
            from src.handlers.registry import create_default_registry

            registry = create_default_registry()
        self.registry = registry
        self.proxy_manager = proxy_manager or ProxyManager()
        self.settings = settings
        self.worker_factory = worker_factory
        if observers is None:
            from src.services.execution_observer import ConsoleExecutionObserver

            observers = (ConsoleExecutionObserver(),)
        self.observers = tuple(observers)

    def run(self) -> ExecutionSummary:
        total = len(self.tasks)
        print(f"[Executor] Queued {total} tasks. Max workers: {self.settings.MAX_WORKERS}")
        for observer in self.observers:
            observer.on_started(total)
        started = time.monotonic()
        if not self.tasks:
            summary = ExecutionSummary([], 0.0)
            for observer in self.observers:
                observer.on_completed(summary)
            return summary

        pending: Dict[Platform, Deque[Task]] = defaultdict(deque)
        for task in self.tasks:
            pending[task.platform].append(task)
        platform_order = deque(pending)

        running_by_platform: Dict[Platform, int] = defaultdict(int)
        running_accounts = set()
        ready_at = defaultdict(float)
        results: List[ExecutionResult] = []

        with ThreadPoolExecutor(
            max_workers=min(total, self.settings.MAX_WORKERS),
            thread_name_prefix="social-worker",
        ) as pool:
            future_to_task = {}
            while any(pending.values()) or future_to_task:
                while len(future_to_task) < self.settings.MAX_WORKERS:
                    task = self._next_task(
                        pending,
                        platform_order,
                        running_by_platform,
                        running_accounts,
                        ready_at,
                    )
                    if task is None:
                        break
                    future = pool.submit(self._process_task, task)
                    future_to_task[future] = task
                    running_by_platform[task.platform] += 1
                    running_accounts.add(task.account_key)

                if future_to_task:
                    completed, _ = wait(future_to_task, return_when=FIRST_COMPLETED)
                    for future in completed:
                        task = future_to_task.pop(future)
                        running_by_platform[task.platform] -= 1
                        running_accounts.remove(task.account_key)
                        ready_at[task.account_key] = time.monotonic() + self.settings.get_cooldown()
                        try:
                            result = future.result()
                        except Exception as exc:
                            result = ExecutionResult(task, ResultCode.INTERNAL_ERROR, error=str(exc))
                        results.append(result)
                        for observer in self.observers:
                            observer.on_result(result, len(results), total)
                elif any(pending.values()):
                    # Cooldowns wait in the dispatcher, not in scarce browser workers.
                    time.sleep(min(0.25, self._next_ready_delay(pending, ready_at)))

        elapsed = time.monotonic() - started
        summary = ExecutionSummary(results, elapsed)
        for observer in self.observers:
            observer.on_completed(summary)
        return summary

    def _next_task(
        self, pending, platform_order, running_by_platform, running_accounts, ready_at
    ):
        now = time.monotonic()
        for _ in range(len(platform_order)):
            platform = platform_order[0]
            platform_order.rotate(-1)
            queue = pending[platform]
            if not queue or running_by_platform[platform] >= self.settings.worker_limit(platform):
                continue
            for _ in range(len(queue)):
                task = queue[0]
                if task.account_key not in running_accounts and ready_at[task.account_key] <= now:
                    return queue.popleft()
                queue.rotate(-1)
        return None

    @staticmethod
    def _next_ready_delay(pending, ready_at) -> float:
        now = time.monotonic()
        deadlines = [ready_at[task.account_key] for queue in pending.values() for task in queue]
        return max(0.001, min(deadlines, default=now) - now)

    def _process_task(self, task: Task) -> ExecutionResult:
        worker = self.worker_factory(
            self.proxy_manager,
            self.registry,
            settings=self.settings,
        )
        return worker.execute(task)
