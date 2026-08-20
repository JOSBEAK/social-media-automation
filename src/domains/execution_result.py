from dataclasses import dataclass
from enum import Enum
from typing import Optional

from src.domains.task import Task


class ResultCode(str, Enum):
    SUCCESS = "success"
    INVALID_TASK = "invalid_task"
    UNSUPPORTED = "unsupported"
    LOGIN_FAILED = "login_failed"
    ACTION_FAILED = "action_failed"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class ExecutionResult:
    task: Task
    code: ResultCode
    attempts: int = 1
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.code is ResultCode.SUCCESS

    def __bool__(self) -> bool:
        return self.success
