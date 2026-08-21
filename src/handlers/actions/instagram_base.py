from src.domains.action_result import ActionResult


class InstagramActionMixin:
    @staticmethod
    def session_error(driver) -> str | None:
        try:
            session_cookie = driver.get_cookie("sessionid")
        except Exception as exc:
            return f"Could not inspect Instagram session cookie: {type(exc).__name__}: {exc}"
        if not session_cookie or not session_cookie.get("value"):
            return (
                "Instagram session is not authenticated: no sessionid cookie was present. "
                "The login screen may have redirected without completing authentication."
            )
        return None

    @classmethod
    def require_session(cls, driver) -> ActionResult | None:
        error = cls.session_error(driver)
        if error:
            print(f"[InstagramSession] {error}", flush=True)
            return ActionResult(False, error)
        print("[InstagramSession] Authenticated session cookie confirmed", flush=True)
        return None
