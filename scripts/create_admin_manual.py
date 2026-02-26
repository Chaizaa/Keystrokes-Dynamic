"""Create or promote an admin user (manual-edit script).

Edit the `USERNAME`, `PASSWORD`, and `EMAIL` variables below, then run:

    python scripts/create_admin_manual.py

This script is intentionally simple so developers can edit it directly
for local setups without using a web endpoint.
"""

import os
import sys
from getpass import getpass

# Project root on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- Editable settings ---
USERNAME = "admin123"
PASSWORD = "admin123"
EMAIL = "darulquro17@gmail.com"
# -------------------------

from app import create_app


def main():
    # Create app context using development config by default
    app = create_app("development")

    with app.app_context():
        from app.models import db, User

        # If PASSWORD is left as placeholder, prompt securely
        global PASSWORD
        if PASSWORD == "changeme":
            try:
                PASSWORD = getpass(f"Password for {USERNAME}: ")
            except Exception:
                PASSWORD = "changeme"

        existing = db.session.query(User).filter_by(username=USERNAME).first()
        if existing:
            print(f"User '{USERNAME}' exists — promoting to admin and updating fields.")
            existing.role = "admin"
            if PASSWORD:
                existing.set_password(PASSWORD)
            if EMAIL:
                existing.email = EMAIL
            db.session.commit()
            print("Updated existing user to admin.")
            return

        # Create new admin user
        u = User(username=USERNAME)
        if PASSWORD:
            u.set_password(PASSWORD)
        if EMAIL:
            u.email = EMAIL
            u.email_verified = True
        u.role = "admin"

        db.session.add(u)
        db.session.commit()

        print(f"Created admin user: {USERNAME}")


if __name__ == "__main__":
    main()
