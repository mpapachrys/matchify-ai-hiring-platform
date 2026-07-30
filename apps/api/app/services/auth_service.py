"""Registration, login, and refresh-token rotation.

No FastAPI imports here on purpose — everything is plain async functions over
the models, so the whole flow is unit-testable without an HTTP client.
"""

from datetime import UTC, datetime

from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    PermissionDeniedError,
)
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    new_token_family,
    refresh_expiry,
    verify_password,
)
from app.models.candidate_profile import CandidateProfile
from app.models.enums import Role
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import RegisterIn


async def register(data: RegisterIn) -> User:
    if data.role is Role.HIRING_MANAGER and not settings.allow_manager_signup:
        raise PermissionDeniedError("Hiring manager accounts are created by invitation only")

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
        full_name=data.full_name.strip(),
        phone=data.phone,
    )

    # Single-tenant bootstrap: the first hiring manager owns organization settings.
    if data.role is Role.HIRING_MANAGER:
        existing_managers = await User.find(User.role == Role.HIRING_MANAGER).count()
        user.is_admin = existing_managers == 0

    try:
        await user.insert()
    except DuplicateKeyError as exc:
        raise ConflictError("An account with that email already exists") from exc

    # Every candidate gets a profile document immediately so the rest of the
    # application never has to handle a missing-profile case.
    await ensure_candidate_profile(user)

    return user


async def ensure_candidate_profile(user: User) -> None:
    """Guarantee a candidate has a profile document.

    Called from both register and login, so clearing candidate_profiles (e.g.
    to demo the CV-to-structured-profile flow from scratch) self-heals on the
    next sign-in and the candidate profile page never 404s.
    """
    if user.role is not Role.CANDIDATE:
        return
    if await CandidateProfile.find_one(CandidateProfile.user_id == user.id) is not None:
        return
    profile = CandidateProfile(user_id=user.id)
    profile.recompute_completion()
    try:
        await profile.insert()
    except DuplicateKeyError:
        pass  # a concurrent login already created it — fine


async def authenticate(email: str, password: str) -> User:
    user = await User.find_one(User.email == email.strip().lower())
    # Same error for unknown email and wrong password — no account enumeration.
    if user is None or not verify_password(password, user.password_hash):
        raise AuthenticationError("Incorrect email or password")
    if not user.is_active:
        raise PermissionDeniedError("This account has been deactivated")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        await user.save()

    user.last_login_at = datetime.now(UTC)
    await user.save()

    # Self-heal a missing profile (e.g. after clearing profiles for a demo) so
    # the candidate profile page never hits a 404 and crashes the render.
    await ensure_candidate_profile(user)
    return user


async def issue_session(
    user: User,
    *,
    user_agent: str | None = None,
    ip: str | None = None,
    family_id: str | None = None,
) -> tuple[str, str]:
    """Mint an access/refresh pair and persist the refresh digest."""
    access = create_access_token(user_id=str(user.id), role=user.role.value)
    refresh = generate_refresh_token()

    await RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh),
        family_id=family_id or new_token_family(),
        user_agent=user_agent,
        ip=ip,
        expires_at=refresh_expiry(),
    ).insert()

    return access, refresh


async def rotate_session(
    raw_refresh: str,
    *,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[User, str, str]:
    """Exchange a refresh token for a fresh pair, invalidating the old one.

    Replay detection: presenting an already-revoked token means the token was
    captured, so the whole family is burned and the user must sign in again.
    """
    digest = hash_refresh_token(raw_refresh)
    record = await RefreshToken.find_one(RefreshToken.token_hash == digest)

    if record is None:
        raise AuthenticationError("Invalid refresh token")

    if record.revoked_at is not None:
        await RefreshToken.find(RefreshToken.family_id == record.family_id).set(
            {RefreshToken.revoked_at: datetime.now(UTC)}
        )
        raise AuthenticationError("Refresh token reuse detected — all sessions revoked")

    if not record.is_usable:
        raise AuthenticationError("Refresh token expired")

    user = await User.get(record.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Account is no longer active")

    record.revoked_at = datetime.now(UTC)
    await record.save()

    access, refresh = await issue_session(
        user, user_agent=user_agent, ip=ip, family_id=record.family_id
    )
    return user, access, refresh


async def revoke_session(raw_refresh: str | None) -> None:
    """Logout. Silent when the token is unknown — nothing useful to report."""
    if not raw_refresh:
        return
    record = await RefreshToken.find_one(
        RefreshToken.token_hash == hash_refresh_token(raw_refresh)
    )
    if record and record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        await record.save()


async def revoke_all_sessions(user: User) -> None:
    await RefreshToken.find(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at == None  # noqa: E711
    ).set({RefreshToken.revoked_at: datetime.now(UTC)})
