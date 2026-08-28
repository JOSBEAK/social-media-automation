# src/interfaces/i_platform_handler.py
from abc import ABC, abstractmethod
from src.domains.platform import Platform
from src.domains.authentication_result import AuthenticationResult
from src.models.account import Account

class IPlatformHandler(ABC):
    @abstractmethod
    def login(self, page, account: Account) -> bool | AuthenticationResult:
        pass

    @abstractmethod
    def get_post_url(self, identifier: str) -> str:
        pass

    @property
    @abstractmethod
    def platform(self) -> Platform:
        pass
