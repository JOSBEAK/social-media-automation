# src/core/worker.py
import time
import traceback

from src.config.settings import Settings
from src.domains.execution_result import ExecutionResult, ResultCode
from src.services.browser_factory import BrowserFactory


class Worker:
    def __init__(
        self,
        proxy_manager,
        registry,
        browser_factory=BrowserFactory,
        settings=Settings,
    ) -> None:
        self.proxy_manager = proxy_manager
        self.registry = registry
        self.browser_factory = browser_factory
        self.settings = settings

    def execute(self, task) -> ExecutionResult:
        validation_error = task.validation_error()
        if validation_error:
            return ExecutionResult(task, ResultCode.INVALID_TASK, error=validation_error)

        platform_handler = self.registry.get_platform(task.platform)
        action_handler = self.registry.get_action(task.platform, task.action)
        if not platform_handler or not action_handler:
            return ExecutionResult(
                task,
                ResultCode.UNSUPPORTED,
                error=f"No handler for {task.platform.value}/{task.action.value}",
            )

        last_error = None
        for attempt in range(1, self.settings.MAX_RETRIES + 2):
            driver = None
            try:
                driver = self.browser_factory.create_driver(proxy=self.proxy_manager.get_next())
                authentication = platform_handler.login(driver, task.account)
                if not authentication:
                    last_error = getattr(authentication, "error", None) or "login failed"
                    if attempt <= self.settings.MAX_RETRIES:
                        time.sleep(self.settings.RETRY_DELAY * attempt)
                        continue
                    return ExecutionResult(task, ResultCode.LOGIN_FAILED, attempt, last_error)

                action_execution = action_handler.execute(driver, task)
                if action_execution:
                    return ExecutionResult(task, ResultCode.SUCCESS, attempt)

                # Avoid blindly retrying a write: the click may have succeeded even
                # if its confirmation selector timed out.
                action_error = getattr(action_execution, "error", None) or "action failed"
                return ExecutionResult(task, ResultCode.ACTION_FAILED, attempt, action_error)
            except Exception:
                last_error = traceback.format_exc(limit=8)
                if attempt <= self.settings.MAX_RETRIES:
                    time.sleep(self.settings.RETRY_DELAY * attempt)
                    continue
                return ExecutionResult(task, ResultCode.INTERNAL_ERROR, attempt, last_error)
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass

        return ExecutionResult(task, ResultCode.INTERNAL_ERROR, error=last_error)
