"""Authentication and role gates.

This module is the security boundary. The Next.js middleware also checks roles,
but purely so the user does not see the wrong shell for a moment — it is a UX
affordance. Nothing here trusts anything the client says about its own role:
the role is read from a signed JWT and re-checked against the database record.
"""

import secrets
from collections.abc import Callable
from typing import Annotated

from beanie import PydanticObjectId
from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.models.enums import Role
from app.models.user import User


def _extract_token(request: Request) -> str | None:
    """Cookie first (browser), then Bearer header (scripts, tests, the AI service)."""
    token = request.cookies.get(settings.access_cookie_name)
    if token:
        return token
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


async def get_optional_user(request: Request) -> User | None:
    """Never raises — used by endpoints that render differently when signed in."""
    token = _extract_token(request)
    if not token:
        return None
    claims = decode_access_token(token)
    if not claims:
        return None
    try:
        user_id = PydanticObjectId(claims["sub"])
    except Exception:
        return None
    user = await User.get(user_id)
    if user is None or not user.is_active:
        return None
    return user


async def get_current_user(request: Request) -> User:
    user = await get_optional_user(request)
    if user is None:
        raise AuthenticationError("Not authenticated")
    return user


def require_role(*roles: Role) -> Callable:
    """Endpoint gate. The role comes from the database record, not the token
    claim, so a role change takes effect on the next request rather than on
    the next login."""

    async def _dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise PermissionDeniedError(
                f"This action requires the {' or '.join(r.value for r in roles)} role"
            )
        return user

    return _dependency


async def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role is not Role.HIRING_MANAGER or not user.is_admin:
        raise PermissionDeniedError("Administrator access required")
    return user


#: Upper bound on a single page. 200 rather than 100 because the kanban board
#: renders a job's whole pipeline at once — capping lower would silently hide
#: candidates from a column.
MAX_PAGE_SIZE = 200


#: Declared as a security scheme rather than read off the raw Request, so it
#: reaches the OpenAPI document — that is what puts the padlock and the
#: "Authorize" button in /docs. Without it the AI team can read the schema but
#: cannot try a single call, and a 401 with no visible way to authenticate is a
#: support ticket waiting to happen.
#:
#: auto_error=False because FastAPI's own missing-credentials response is a bare
#: 403; we want our error shape and our status codes.
service_token_scheme = HTTPBearer(
    scheme_name="ServiceToken",
    description=(
        "Shared token for the graph export, not a user login. Paste the value of "
        "INBOUND_AI_TOKEN — Swagger adds the `Bearer ` prefix itself."
    ),
    auto_error=False,
)


async def require_service_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(service_token_scheme)],
) -> None:
    """Gate for machine-to-machine endpoints.

    Deliberately not a user JWT: the AI service is not a person, should not need
    an account, and should keep working when staff come and go. An unset token
    disables the endpoints rather than leaving them open — failing closed is the
    only safe default for an endpoint that returns candidates' personal data.
    """
    expected = settings.inbound_ai_token
    if not expected:
        raise PermissionDeniedError(
            "Service access is not configured. Set INBOUND_AI_TOKEN to enable it."
        )

    presented = credentials.credentials.strip() if credentials else ""

    # Constant-time: a plain == leaks the token's length and prefix by timing.
    if not presented or not secrets.compare_digest(presented, expected):
        raise AuthenticationError("Invalid service token")


class Pagination:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
    ):
        self.page = page
        self.page_size = page_size

    @property
    def skip(self) -> int:
        return (self.page - 1) * self.page_size


# ── Ergonomic aliases used throughout the route modules ──
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
CurrentCandidate = Annotated[User, Depends(require_role(Role.CANDIDATE))]
CurrentManager = Annotated[User, Depends(require_role(Role.HIRING_MANAGER))]
AdminUser = Annotated[User, Depends(require_admin)]
Paginate = Annotated[Pagination, Depends()]
ServiceCaller = Annotated[None, Depends(require_service_token)]
