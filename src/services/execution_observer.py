from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.executor import ExecutionSummary
    from src.domains.execution_result import ExecutionResult


class ConsoleExecutionObserver:
    def on_started(self, total: int) -> None:
        return None

    def on_result(self, result: ExecutionResult, completed: int, total: int) -> None:
        marker = "✅" if result.success else "❌"
        detail = f" ({result.error.splitlines()[-1][:100]})" if result.error else ""
        print(
            f"[Executor] Progress: {completed}/{total} | {marker} "
            f"{result.task.platform.value}:{result.task.account.username} "
            f"{result.code.value}{detail}"
        )

    def on_completed(self, summary: ExecutionSummary) -> None:
        print("\n" + "=" * 60)
        print("✅ EXECUTION COMPLETE!")
        print(f"   Total: {len(summary.results)}")
        print(f"   Success: {summary.succeeded}")
        print(f"   Failed: {summary.failed}")
        print(f"   Time: {summary.elapsed_seconds / 60:.2f} min")
        print("=" * 60)
