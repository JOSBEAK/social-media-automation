# src/config/settings.py
import os
import random

from src.domains.platform import Platform


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Runtime controls. Every value can be changed without editing source code."""

    MAX_WORKERS = max(1, int(os.getenv("SOCIAL_MAX_WORKERS", "5")))
    MAX_RETRIES = max(0, int(os.getenv("SOCIAL_MAX_RETRIES", "1")))
    RETRY_DELAY = max(0.0, float(os.getenv("SOCIAL_RETRY_DELAY", "2")))
    MIN_COOLDOWN = max(0.0, float(os.getenv("SOCIAL_MIN_COOLDOWN", "0")))
    MAX_COOLDOWN = max(MIN_COOLDOWN, float(os.getenv("SOCIAL_MAX_COOLDOWN", "0")))
    HEADLESS = _env_bool("SOCIAL_HEADLESS", False)
    IMPLICIT_WAIT = max(0.0, float(os.getenv("SOCIAL_IMPLICIT_WAIT", "10")))
    LOGIN_TYPING_MIN = max(0.0, float(os.getenv("SOCIAL_LOGIN_TYPING_MIN", "0.05")))
    LOGIN_TYPING_MAX = max(
        LOGIN_TYPING_MIN, float(os.getenv("SOCIAL_LOGIN_TYPING_MAX", "0.15"))
    )
    LOGIN_SETTLE_SECONDS = max(0.0, float(os.getenv("SOCIAL_LOGIN_SETTLE_SECONDS", "6")))
    JOB_WORKERS = max(1, int(os.getenv("SOCIAL_JOB_WORKERS", "1")))
    JOB_POLL_INTERVAL = max(0.1, float(os.getenv("SOCIAL_JOB_POLL_INTERVAL", "0.5")))
    MAX_CSV_BYTES = max(1024, int(os.getenv("SOCIAL_MAX_CSV_BYTES", str(5 * 1024 * 1024))))
    MAX_ACCOUNTS_PER_BATCH = max(
        1, int(os.getenv("SOCIAL_MAX_ACCOUNTS_PER_BATCH", "10000"))
    )
    DATA_DIR = os.getenv("SOCIAL_DATA_DIR", "data")
    DATABASE_PATH = os.getenv("SOCIAL_DATABASE_PATH", os.path.join(DATA_DIR, "social.db"))
    CREDENTIAL_KEY = os.getenv("SOCIAL_CREDENTIAL_KEY")

    # Example: SOCIAL_PLATFORM_WORKERS="instagram=2,twitter=3"
    _PLATFORM_WORKERS = os.getenv("SOCIAL_PLATFORM_WORKERS", "")

    @classmethod
    def get_cooldown(cls) -> float:
        return random.uniform(cls.MIN_COOLDOWN, cls.MAX_COOLDOWN)

    @classmethod
    def worker_limit(cls, platform: Platform) -> int:
        limits = {}
        for item in cls._PLATFORM_WORKERS.split(","):
            if "=" not in item:
                continue
            name, value = item.split("=", 1)
            try:
                limits[Platform.parse(name.strip())] = max(1, int(value))
            except (ValueError, TypeError):
                continue
        return min(cls.MAX_WORKERS, limits.get(platform, cls.MAX_WORKERS))
