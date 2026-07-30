from fastapi import APIRouter, Request, Response, status

from app.api.cookies import clear_session_cookies, set_session_cookies
from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.security import hash_password, verify_password
from app.schemas.auth import (
    LoginIn,
    PasswordChangeIn,
    RegisterIn,
    SessionOut,
    UserOut,
    UserUpdateIn,
)
from app.schemas.common import MessageOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("user-agent"), request.client.host if request.client else None


@router.post("/register", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, request: Request, response: Response) -> SessionOut:
    user = await auth_service.register(data)
    ua, ip = _client_meta(request)
    access, refresh = await auth_service.issue_session(user, user_agent=ua, ip=ip)
    set_session_cookies(response, access=access, refresh=refresh, role=user.role)
    return SessionOut(user=UserOut.from_user(user))


@router.post("/login", response_model=SessionOut)
async def login(data: LoginIn, request: Request, response: Response) -> SessionOut:
    user = await auth_service.authenticate(data.email, data.password)
    ua, ip = _client_meta(request)
    access, refresh = await auth_service.issue_session(user, user_agent=ua, ip=ip)
    set_session_cookies(response, access=access, refresh=refresh, role=user.role)
    return SessionOut(user=UserOut.from_user(user))


@router.post("/refresh", response_model=SessionOut)
async def refresh_session(request: Request, response: Response) -> SessionOut:
    token = request.cookies.get(settings.refresh_cookie_name)
    if not token:
        raise AuthenticationError("No refresh token")

    ua, ip = _client_meta(request)
    user, access, refresh = await auth_service.rotate_session(token, user_agent=ua, ip=ip)
    set_session_cookies(response, access=access, refresh=refresh, role=user.role)
    return SessionOut(user=UserOut.from_user(user))


@router.post("/logout", response_model=MessageOut)
async def logout(request: Request, response: Response) -> MessageOut:
    await auth_service.revoke_session(request.cookies.get(settings.refresh_cookie_name))
    clear_session_cookies(response)
    return MessageOut(detail="Signed out")


@router.get("/me", response_model=SessionOut)
async def me(user: CurrentUser) -> SessionOut:
    return SessionOut(user=UserOut.from_user(user))


@router.patch("/me", response_model=SessionOut)
async def update_me(data: UserUpdateIn, user: CurrentUser) -> SessionOut:
    # getattr rather than model_dump(), consistent with the other update paths:
    # dumping would flatten any nested model into a dict, and Beanie documents
    # do not validate on assignment. All fields here are scalars today.
    for key in data.model_fields_set:
        value = getattr(data, key)
        if value is not None:
            setattr(user, key, value)
    await user.save()
    return SessionOut(user=UserOut.from_user(user))


@router.post("/change-password", response_model=MessageOut)
async def change_password(
    data: PasswordChangeIn, user: CurrentUser, response: Response
) -> MessageOut:
    if not verify_password(data.current_password, user.password_hash):
        raise AuthenticationError("Current password is incorrect")

    user.password_hash = hash_password(data.new_password)
    await user.save()

    # A password change invalidates every session, including this one.
    await auth_service.revoke_all_sessions(user)
    clear_session_cookies(response)
    return MessageOut(detail="Password updated — please sign in again")
