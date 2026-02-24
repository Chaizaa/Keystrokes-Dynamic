#!/usr/bin/env python3
"""Debug helper: attempt admin-delete flow for a user inside a nested transaction and print errors without committing."""
import traceback

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models import db, User, AdminAudit

app = create_app()
app.app_context().push()

TARGET_ID = 3

print(f"Starting debug delete flow for user id={TARGET_ID}")

try:
    with db.session.begin_nested():
        user = db.session.get(User, TARGET_ID)
        if not user:
            print("User not found")
        else:
            print(f"Found user: {user.username} (role={user.role})")

            try:
                admin_count = User.query.filter(User.role == 'admin').count()
                print('Admin count:', admin_count)
                if user.is_admin() and admin_count <= 1:
                    print('Would not delete: last admin')
            except Exception:
                print('Error checking admin count:')
                traceback.print_exc()

            try:
                AdminAudit.query.filter((AdminAudit.user_id == user.id) | (AdminAudit.username == user.username)).delete(synchronize_session=False)
                print('AdminAudit entries delete attempted')
            except Exception:
                print('AdminAudit delete failed:')
                traceback.print_exc()

            try:
                from app.models import EnrollmentVector, FeatureVector, KeystrokeVector, LoginAttempt
                EnrollmentVector.query.filter((EnrollmentVector.user_id == user.id) | (EnrollmentVector.username == user.username)).delete(synchronize_session=False)
                FeatureVector.query.filter((FeatureVector.user_id == user.id) | (FeatureVector.username == user.username)).delete(synchronize_session=False)
                KeystrokeVector.query.filter((KeystrokeVector.user_id == user.id) | (KeystrokeVector.username == user.username)).delete(synchronize_session=False)
                LoginAttempt.query.filter((LoginAttempt.user_id == user.id) | (LoginAttempt.username == user.username)).delete(synchronize_session=False)
                print('Vector deletions attempted')
            except Exception:
                print('Vector deletions failed:')
                traceback.print_exc()

            try:
                    # Use class-level delete to avoid triggering relationship load
                    db.session.query(User).filter(User.id == user.id).delete(synchronize_session=False)
                    db.session.flush()
                    print('User deletion (class-level) flushed (not committed)')
            except Exception:
                print('User deletion failed (during flush):')
                traceback.print_exc()

    print('Nested transaction complete — rolling back outer session to avoid changes')
    db.session.rollback()
except Exception:
    print('Unexpected error in debug flow:')
    traceback.print_exc()

print('Debug script finished')
