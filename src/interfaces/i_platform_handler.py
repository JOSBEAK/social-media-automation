# src/interfaces/i_platform_handler.py
from abc import ABC, abstractmethod
from selenium.webdriver.remote.webdriver import WebDriver
from src.domains.platform import Platform
from src.models.account import Account

class IPlatformHandler(ABC):
    @abstractmethod
    def login(self, driver: WebDriver, account: Account) -> bool:
        pass

    @abstractmethod
    def get_post_url(self, identifier: str) -> str:
        pass

    @property
    @abstractmethod
    def platform(self) -> Platform:
        pass
