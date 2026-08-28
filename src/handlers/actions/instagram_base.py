from src.domains.action_result import ActionResult


class InstagramActionMixin:
    @staticmethod
    def session_error(page) -> str | None:
        try:
            cookies = page.context.cookies("https://www.instagram.com")
            session_cookie = next((c for c in cookies if c["name"] == "sessionid"), None)
        except Exception as exc:
            return f"Could not inspect Instagram session cookie: {type(exc).__name__}: {exc}"
        if not session_cookie or not session_cookie.get("value"):
            return (
                "Instagram session is not authenticated: no sessionid cookie was present. "
                "The login screen may have redirected without completing authentication."
            )
        return None

    @classmethod
    def require_session(cls, page) -> ActionResult | None:
        error = cls.session_error(page)
        if error:
            print(f"[InstagramSession] {error}", flush=True)
            return ActionResult(False, error)
        print("[InstagramSession] Authenticated session cookie confirmed", flush=True)
        return None
