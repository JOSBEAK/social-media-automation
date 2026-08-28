import unittest

from src.handlers.actions.instagram_base import InstagramActionMixin


class FakeContext:
    """Simulates a Playwright BrowserContext with cookies()."""
    def __init__(self, cookie=None):
        self._cookies = [cookie] if cookie else []

    def cookies(self, url=None):
        return self._cookies


class FakePage:
    """Simulates a Playwright Page with a context attribute."""
    def __init__(self, cookie=None):
        self.context = FakeContext(cookie)


class InstagramSessionTests(unittest.TestCase):
    def test_rejects_post_action_without_session_cookie(self):
        result = InstagramActionMixin.require_session(FakePage())

        self.assertFalse(result)
        self.assertIn("no sessionid cookie", result.error)

    def test_accepts_authenticated_session_cookie(self):
        result = InstagramActionMixin.require_session(
            FakePage({"name": "sessionid", "value": "active-session"})
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
