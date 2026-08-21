import unittest

from src.handlers.actions.instagram_base import InstagramActionMixin


class CookieDriver:
    def __init__(self, cookie=None):
        self.cookie = cookie

    def get_cookie(self, name):
        return self.cookie if name == "sessionid" else None


class InstagramSessionTests(unittest.TestCase):
    def test_rejects_post_action_without_session_cookie(self):
        result = InstagramActionMixin.require_session(CookieDriver())

        self.assertFalse(result)
        self.assertIn("no sessionid cookie", result.error)

    def test_accepts_authenticated_session_cookie(self):
        result = InstagramActionMixin.require_session(
            CookieDriver({"name": "sessionid", "value": "active-session"})
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
