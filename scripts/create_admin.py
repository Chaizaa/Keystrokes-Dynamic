"""Create an admin user (one-time setup script).

Usage:
    python scripts/create_admin.py --username admin --password secret

This script creates a user and assigns role='admin'.
"""

import argparse
import sys
import os

# Ensure project root is on sys.path so `from app import create_app` works
# whether this script is executed from repository root or the `scripts/` directory.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--email", required=False)

    args = parser.parse_args()

    app = create_app("development")

    with app.app_context():
        from app.models import db, User

        # Check existing user
        existing = db.session.query(User).filter_by(username=args.username).first()
        if existing:
            print(f"User '{args.username}' already exists. Updating role to 'admin'.")
            existing.role = "admin"
            if args.password:
                existing.set_password(args.password)
            if args.email:
                existing.email = args.email
            db.session.commit()
            print("Updated existing user to admin.")
            return

        # Create new user
        u = User(username=args.username)
        u.set_password(args.password)
        if args.email:
            u.email = args.email
            u.email_verified = True
        u.role = "admin"

        db.session.add(u)
        db.session.commit()

        print(f"Created admin user: {args.username}")


if __name__ == "__main__":
    main()
