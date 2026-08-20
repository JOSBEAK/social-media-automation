from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.executor import ExecutionSummary
    from src.domains.execution_result import ExecutionResult


class IExecutionObserver(Protocol):
    def on_started(self, total: int) -> None: ...

    def on_result(self, result: "ExecutionResult", completed: int, total: int) -> None: ...

    def on_completed(self, summary: "ExecutionSummary") -> None: ...
