"""Session cookies.

Access and refresh tokens are httpOnly, so no script — including one injected
via XSS — can read them. Because Next.js proxies /api/v1/* to this service,
the browser sees them as first-party cookies on localhost:3000, which also
means no CORS preflight and no cross-site cookie rules to fight.
"""

from fastapi import Response

from app.core.config import settings
from app.models.enums import Role

_ACCESS_PATH = "/"
_REFRESH_PATH = "/"


def _common_kwargs() -> dict:
    kwargs: dict = {
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "path": _ACCESS_PATH,
    }
    if settings.cookie_domain:
        kwargs["domain"] = settings.cookie_domain
    return kwargs


def set_session_cookies(response: Response, *, access: str, refresh: str, role: Role) -> None:
    common = _common_kwargs()

    response.set_cookie(
        settings.access_cookie_name,
        access,
        httponly=True,
        max_age=settings.access_token_ttl_minutes * 60,
        **common,
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        refresh,
        httponly=True,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        **{**common, "path": _REFRESH_PATH},
    )
    # Readable by JS by design. The Next.js middleware uses it to pick which
    # shell to render; it is never consulted for authorization.
    response.set_cookie(
        settings.role_cookie_name,
        role.value,
        httponly=False,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        **common,
    )


def clear_session_cookies(response: Response) -> None:
    common = _common_kwargs()
    for name in (
        settings.access_cookie_name,
        settings.refresh_cookie_name,
        settings.role_cookie_name,
    ):
        response.delete_cookie(name, **common)
