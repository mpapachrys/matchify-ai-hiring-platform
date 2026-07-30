"""Create (or promote) a hiring manager from the command line.

Manager self-signup is disabled in production (ALLOW_MANAGER_SIGNUP=false), so
there is no UI path to the first manager after the database is emptied. This is
that path.

    # password from an env var — never on the command line, never in shell history
    MANAGER_PASSWORD=... python -m app.db.create_manager \
        --email you@example.com --name "Your Name" --admin

    # an email that already exists (e.g. a candidate you registered) can be
    # converted rather than rejected
    MANAGER_PASSWORD=... python -m app.db.create_manager \
        --email you@example.com --name "Your Name" --admin --promote

The password is read from MANAGER_PASSWORD, or prompted for when run
interactively. It is never taken as a flag, so it cannot leak into `ps`, shell
history, or CI logs.
"""

import argparse
import asyncio
import getpass
import logging
import os
import sys

from app.core.security import hash_password
from app.models.enums import Role
from app.models.user import User

logger = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 8


def _read_password() -> str:
    password = os.getenv("MANAGER_PASSWORD")
    if password is None and sys.stdin.isatty():
        password = getpass.getpass("Manager password: ")
    if not password:
        raise SystemExit(
            "No password given. Set MANAGER_PASSWORD, or run interactively to be prompted."
        )
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return password


async def create_manager(
    email: str, name: str, *, is_admin: bool, promote: bool, password: str
) -> User:
    email = email.strip().lower()
    existing = await User.find_one(User.email == email)

    if existing is not None:
        if not promote:
            raise SystemExit(
                f"{email} already exists (role: {existing.role.value}). "
                f"Pass --promote to convert it to a hiring manager and reset its password."
            )
        existing.role = Role.HIRING_MANAGER
        existing.is_admin = is_admin
        existing.full_name = name.strip() or existing.full_name
        existing.password_hash = hash_password(password)
        existing.is_active = True
        existing.is_email_verified = True
        await existing.save()
        logger.info("promoted %s to hiring manager (admin=%s)", email, is_admin)
        return existing

    user = User(
        email=email,
        password_hash=hash_password(password),
        role=Role.HIRING_MANAGER,
        full_name=name.strip(),
        is_admin=is_admin,
        is_active=True,
        is_email_verified=True,
    )
    await user.insert()
    logger.info("created hiring manager %s (admin=%s)", email, is_admin)
    return user


async def _main() -> None:
    from app.db import mongo

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Create or promote a hiring manager")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True, help="Full name")
    parser.add_argument(
        "--admin", action="store_true", help="Grant admin (owns organization settings)"
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="If the email already exists, convert it instead of failing",
    )
    args = parser.parse_args()

    password = _read_password()

    await mongo.connect()
    try:
        await create_manager(
            args.email,
            args.name,
            is_admin=args.admin,
            promote=args.promote,
            password=password,
        )
    finally:
        await mongo.disconnect()


if __name__ == "__main__":
    asyncio.run(_main())
