# src/domains/platform.py
from enum import Enum

class Platform(str, Enum):
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    FACEBOOK = "facebook"

    @classmethod
    def parse(cls, value: "Platform | str") -> "Platform":
        """Parse user-facing platform names while keeping one canonical key."""
        if isinstance(value, cls):
            return value

        normalized = value.strip().lower()
        aliases = {"x": cls.TWITTER, "x.com": cls.TWITTER}
        if normalized in aliases:
            return aliases[normalized]
        return cls(normalized)
