# src/models/account.py
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

@dataclass
class Account:
    username: str
    password: str
    platform: str = "instagram"
    # X can request an email, phone number, or username as an extra login check.
    verification_identifier: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.platform = self.platform.strip().lower()
