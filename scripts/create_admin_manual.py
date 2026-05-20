"""Create or promote an admin account from the command line.

The interactive `/admin/register` endpoint was removed to avoid exposing admin
creation publicly. Run this script on the server or a trusted dev machine.

Usage:
    # Interactive (prompts for username, email, password):
    python scripts/create_admin_manual.py

    # Non-interactive (good for CI / one-shot provisioning):
    python scripts/create_admin_manual.py --username admin --email admin@example.com --yes

    # Promote an existing user:
    python scripts/create_admin_manual.py --username existing_user --promote --yes

    # Pass password on the command line (avoid on shared machines):
    python scripts/create_admin_manual.py --username admin --email a@x.com --password 'secret' --yes

Exit codes:
    0  success (or already-admin no-op for --promote)
    1  user aborted at confirmation prompt
    2  invalid input or precondition failure (duplicate username, bad email, etc.)
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sys
from pathlib import Path

# Make the project importable when run as `python scripts/create_admin_manual.py`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app import create_app
from app.models import AdminAudit, User, db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LEN = 8


def _prompt_password() -> str:
    while True:
        p1 = getpass.getpass("Password: ")
        if len(p1) < MIN_PASSWORD_LEN:
            print(f"  Password too short (min {MIN_PASSWORD_LEN} chars)")
            continue
        p2 = getpass.getpass("Confirm password: ")
        if p1 != p2:
            print("  Passwords don't match")
            continue
        return p1


def _confirm(prompt: str, *, auto_yes: bool) -> bool:
    if auto_yes:
        return True
    return input(f"{prompt} [y/N]: ").strip().lower() == "y"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create or promote an admin account.")
    p.add_argument("--username", help="Username for the admin account")
    p.add_argument("--email", help="Email address (used for password reset)")
    p.add_argument(
        "--password",
        help="Password (omit to be prompted; avoid passing on shared machines)",
    )
    p.add_argument(
        "--promote",
        action="store_true",
        help="Promote an existing user to admin instead of creating a new account",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts (for scripted runs)",
    )
    p.add_argument(
        "--env",
        default=os.environ.get("FLASK_ENV", "development"),
        help="Flask environment name (default: $FLASK_ENV or 'development')",
    )
    return p.parse_args()


def _promote_existing(user: User, *, auto_yes: bool) -> int:
    if user.is_admin():
        print(f"User {user.username!r} is already an admin. Nothing to do.")
        return 0
    if not _confirm(f"Promote {user.username!r} (role={user.role!r}) -> admin?", auto_yes=auto_yes):
        print("Aborted.")
        return 1
    user.role = "admin"
    AdminAudit.log(
        action=AdminAudit.ACTION_ROLE_CHANGED,
        user_id=user.id,
        username=user.username,
        details={"new_role": "admin", "source": "create_admin_manual.py"},
    )
    db.session.commit()
    print(f"OK: {user.username!r} is now an admin")
    return 0


def _create_new(username: str, email: str, password: str, *, auto_yes: bool) -> int:
    print(f"Create admin: username={username!r}, email={email!r}, role='admin'")
    if not _confirm("Confirm?", auto_yes=auto_yes):
        print("Aborted.")
        return 1
    user = User(
        username=username,
        email=email,
        email_verified=True,
        role="admin",
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  # populate user.id before audit log

    AdminAudit.log(
        action=AdminAudit.ACTION_ADMIN_CREATED,
        user_id=user.id,
        username=user.username,
        details={"source": "create_admin_manual.py"},
    )
    db.session.commit()
    print(f"OK: created admin {user.username!r} (id={user.id})")
    return 0


def main() -> int:
    args = _parse_args()
    app = create_app(args.env)

    with app.app_context():
        username = (args.username or input("Username: ")).strip()
        if not username:
            print("ERROR: username is required", file=sys.stderr)
            return 2

        existing = db.session.execute(
            select(User).where(User.username == username)
        ).scalars().first()

        if args.promote:
            if not existing:
                print(f"ERROR: user {username!r} not found (cannot promote)", file=sys.stderr)
                return 2
            return _promote_existing(existing, auto_yes=args.yes)

        if existing:
            print(
                f"ERROR: user {username!r} already exists. "
                f"Use --promote to elevate them, or delete the account first.",
                file=sys.stderr,
            )
            return 2

        email = (args.email or input("Email: ")).strip()
        if not EMAIL_RE.match(email):
            print(f"ERROR: {email!r} is not a valid email address", file=sys.stderr)
            return 2

        password = args.password or _prompt_password()
        if len(password) < MIN_PASSWORD_LEN:
            print(
                f"ERROR: password must be at least {MIN_PASSWORD_LEN} characters",
                file=sys.stderr,
            )
            return 2

        return _create_new(username, email, password, auto_yes=args.yes)


if __name__ == "__main__":
    raise SystemExit(main())
