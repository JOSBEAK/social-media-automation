# src/domains/action_type.py
from enum import Enum

class ActionType(str, Enum):
    LIKE = "like"
    COMMENT = "comment"
    REPOST = "repost"

    @classmethod
    def parse(cls, value: "ActionType | str") -> "ActionType":
        if isinstance(value, cls):
            return value
        normalized = value.strip().lower()
        aliases = {"reply": cls.COMMENT, "retweet": cls.REPOST, "share": cls.REPOST}
        if normalized in aliases:
            return aliases[normalized]
        return cls(normalized)
