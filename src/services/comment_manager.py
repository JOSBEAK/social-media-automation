# src/services/comment_manager.py
import random

class CommentManager:
    TEMPLATES = [
        "Great post! 👏", "Love this! 🔥", "Amazing content! 💯",
        "So inspiring! ✨", "This is awesome! 🌟", "Keep it up! 💪",
        "Love it! ❤️", "Brilliant! 🎯", "Fantastic! 🎉",
        "So good! 🙌", "This made my day! 😄", "Absolutely love this! 💖"
    ]
    
    def __init__(self, custom_comments: list = None):
        self.comments = custom_comments or self.TEMPLATES.copy()
    
    def generate_comment(self, index: int = None) -> str:
        if index is not None:
            return self.comments[index % len(self.comments)]
        return random.choice(self.comments)
