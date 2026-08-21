# src/interfaces/i_action_handler.py
from abc import ABC, abstractmethod
from selenium.webdriver.remote.webdriver import WebDriver
from src.domains.platform import Platform
from src.domains.action_type import ActionType
from src.domains.task import Task
from src.domains.action_result import ActionResult

class IActionHandler(ABC):
    @abstractmethod
    def execute(self, driver: WebDriver, task: Task) -> bool | ActionResult:
        pass

    @property
    @abstractmethod
    def platform(self) -> Platform:
        pass

    @property
    @abstractmethod
    def action_type(self) -> ActionType:
        pass
