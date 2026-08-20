# src/domains/task.py
from dataclasses import dataclass, field
from typing import Any, Dict
from urllib.parse import urlparse
from src.models.account import Account
from src.domains.platform import Platform
from src.domains.action_type import ActionType

@dataclass
class Task:
    account: Account
    platform: Platform
    action: ActionType
    target_url: str
    params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.platform = Platform.parse(self.platform)
        self.action = ActionType.parse(self.action)
        if self.params is None:
            self.params = {}

    @property
    def account_key(self) -> tuple[Platform, str]:
        return self.platform, self.account.username.casefold()

    def validation_error(self) -> str | None:
        if Platform.parse(self.account.platform) != self.platform:
            return "task platform does not match account platform"
        parsed = urlparse(self.target_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "target_url must be an absolute http(s) URL"

        allowed_hosts = {
            Platform.INSTAGRAM: {"instagram.com", "www.instagram.com"},
            Platform.TWITTER: {
                "twitter.com",
                "www.twitter.com",
                "mobile.twitter.com",
                "x.com",
                "www.x.com",
            },
            Platform.FACEBOOK: {"facebook.com", "www.facebook.com", "m.facebook.com"},
        }
        if parsed.netloc.lower() not in allowed_hosts.get(self.platform, set()):
            return f"target_url host does not match {self.platform.value}"
        return None
