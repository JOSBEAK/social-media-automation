from dataclasses import dataclass


@dataclass(frozen=True)
class AuthenticationResult:
    success: bool
    error: str | None = None

    def __bool__(self) -> bool:
        return self.success
