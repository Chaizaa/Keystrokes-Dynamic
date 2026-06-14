"""
Authentication Service - User authentication and registration logic.
Handles password validation, user creation, and login verification.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from flask import session
from flask_login import login_user, logout_user
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.models import User, UsersVector, db


class AuthService:
    """
    Service class for authentication operations.
    Handles user registration, login, and password management.
    """

    def __init__(self, min_username: int = 3, max_username: int = 50):
        self.MIN_USERNAME_LENGTH = min_username
        self.MAX_USERNAME_LENGTH = max_username
        # Passwords can be short for research purposes, but not empty.
        self.MIN_PASSWORD_LENGTH = 1
        self.MAX_PASSWORD_LENGTH = 128

    def validate_username(self, username: str) -> Dict[str, Any]:
        if not username:
            return {"valid": False, "message": "Username cannot be empty"}
        if len(username) < self.MIN_USERNAME_LENGTH:
            return {"valid": False, "message": f"Username must be at least {self.MIN_USERNAME_LENGTH} chars"}
        if len(username) > self.MAX_USERNAME_LENGTH:
            return {"valid": False, "message": f"Username must be less than {self.MAX_USERNAME_LENGTH} chars"}
        if not username.replace("_", "").replace("-", "").isalnum():
            return {"valid": False, "message": "Username can only contain letters, numbers, hyphens, and underscores"}
        return {"valid": True, "message": "Username is valid"}

    def validate_password(self, password: str) -> Dict[str, Any]:
        if not password:
            return {"valid": False, "message": "Password cannot be empty"}
        if len(password) < self.MIN_PASSWORD_LENGTH:
            return {"valid": False, "message": "Password is too short"}
        if len(password) > self.MAX_PASSWORD_LENGTH:
            return {"valid": False, "message": "Password is too long"}
        return {"valid": True, "message": "Password is valid"}

    def check_username_availability(self, username: str) -> Dict[str, Any]:
        """Check if username is available and return enrollment counts."""
        val = self.validate_username(username)
        if not val["valid"]:
            return {"available": False, "exists": False, "reason": "invalid_format", "message": val["message"]}

        try:
            user_exists = db.session.execute(select(User.id).where(User.username == username)).first() is not None
            enroll_count = db.session.execute(
                select(func.count()).select_from(UsersVector).where(UsersVector.username == username)
                .where(UsersVector.event_type == "enrollment")
            ).scalar_one() or 0
        except OperationalError as e:
            print(f"[WARN] DB error in check_username_availability: {e}")
            return {
                "available": False, "exists": False, "reason": "db_error", 
                "enrollment_count": 0, "message": "Database error"
            }

        if user_exists:
            return {
                "available": False, "exists": True, "reason": "already_exists",
                "enrollment_count": enroll_count,
                "message": f"Username '{username}' is already taken",
            }

        if enroll_count > 0:
            return {
                "available": False, "exists": False, "reason": "resumable",
                "enrollment_count": enroll_count,
                "message": f"Resume enrollment ({enroll_count} samples collected)",
            }

        return {
            "available": True, "exists": False, "reason": "new", 
            "enrollment_count": 0, "message": "Username is available"
        }

    def get_user_by_username(self, username: str) -> Optional[User]:
        return db.session.execute(select(User).where(User.username == username)).scalars().first()

    def get_user_by_email(self, email: str) -> Optional[User]:
        return db.session.execute(select(User).where(User.email == email)).scalars().first()

    def get_user_by_identifier(self, identifier: str) -> Optional[User]:
        if not identifier: return None
        if "@" in identifier:
            user = self.get_user_by_email(identifier)
            if user: return user
        return self.get_user_by_username(identifier)

    def create_user(self, username: str, password: str, email: Optional[str] = None) -> Dict[str, Any]:
        """Simplified user creation using ORM."""
        val_u = self.validate_username(username)
        if not val_u["valid"]: return {"success": False, "message": val_u["message"]}
        
        val_p = self.validate_password(password)
        if not val_p["valid"]: return {"success": False, "message": val_p["message"]}

        if self.get_user_by_username(username):
            return {"success": False, "message": "Username already exists", "error_code": "USERNAME_TAKEN"}

        if email:
            existing_email = self.get_user_by_email(email)
            if existing_email and existing_email.username != username:
                return {
                    "success": False,
                    "message": "Email already registered to another account",
                    "error_code": "EMAIL_TAKEN",
                }

        try:
            new_user = User(username=username, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            return {"success": True, "user": new_user, "message": "User created successfully"}
        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": f"Failed to create user: {str(e)}"}

    def verify_password(self, user: User | str, password: str) -> Tuple[bool, Optional[User]]:
        u = self.get_user_by_username(user) if isinstance(user, str) else user
        if not u or not password: return False, None
        valid = u.check_password(password)
        return (True, u) if valid else (False, None)

    def verify_two_factor_token(self, username: str, token: str) -> bool:
        """Verify a TOTP token against the user's stored secret."""
        user = self.get_user_by_username(username)
        if not user or not user.two_factor_secret:
            return False
        
        import pyotp
        totp = pyotp.TOTP(user.two_factor_secret)
        return totp.verify(token)

    def login_user_session(self, user: User, remember: bool = False) -> bool:
        try:
            login_user(user, remember=remember)
            session["username"] = user.username
            session["user_id"] = user.id
            # Snapshot the session-invalidation version. A password reset bumps
            # User.session_token_version; the user_loader rejects any session
            # whose snapshot no longer matches, so a reset kills stale sessions.
            session["stv"] = user.session_token_version
            return True
        except Exception as e:
            print(f"[ERROR] login_user_session: {e}")
            return False

    def logout_user_session(self) -> bool:
        try:
            logout_user()
            session.pop("username", None)
            session.pop("user_id", None)
            return True
        except Exception as e:
            print(f"[ERROR] logout_user_session: {e}")
            return False

    def change_password(self, username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        valid, user = self.verify_password(username, old_password)
        if not valid or not user: return False, "Current password is incorrect"
        
        val_n = self.validate_password(new_password)
        if not val_n["valid"]: return False, val_n["message"]

        try:
            user.set_password(new_password)
            db.session.commit()
            return True, "Password changed successfully"
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to change password: {str(e)}"
