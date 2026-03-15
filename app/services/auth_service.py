"""
Authentication Service - User authentication and registration logic
Handles password validation, user creation, and login verification
"""

from typing import Dict, Optional, Tuple

from flask import session
from flask_login import login_user, logout_user
from sqlalchemy import func, or_, select
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import UsersVector
from app.models import User
from app.models import db as sqlalchemy_db


class AuthService:
    """
    Service class for authentication operations
    Handles user registration, login, and password management
    """

    def __init__(self):
        """Initialize authentication service with database connection"""
        # Password requirements (keystroke-based: allow short passwords)
        self.MIN_PASSWORD_LENGTH = 1
        self.MAX_PASSWORD_LENGTH = 128
        self.MIN_USERNAME_LENGTH = 3
        self.MAX_USERNAME_LENGTH = 50

    def validate_username(self, username: str) -> Dict:
        """
        Validate username format

        Args:
            username: Username to validate

        Returns:
            Dict with 'valid' (bool) and 'message' (str)
        """
        if not username:
            return {"valid": False, "message": "Username cannot be empty"}

        if len(username) < self.MIN_USERNAME_LENGTH:
            return {
                "valid": False,
                "message": f"Username must be at least {self.MIN_USERNAME_LENGTH} characters",
            }

        if len(username) > self.MAX_USERNAME_LENGTH:
            return {
                "valid": False,
                "message": f"Username must be less than {self.MAX_USERNAME_LENGTH} characters",
            }

        # Check alphanumeric
        if not username.replace("_", "").replace("-", "").isalnum():
            return {
                "valid": False,
                "message": "Username can only contain letters, numbers, hyphens, and underscores",
            }

        return {"valid": True, "message": "Username is valid"}

    def validate_password(self, password: str) -> Dict:
        """
        Validate password strength

        Args:
            password: Password to validate

        Returns:
            Dict with 'valid' (bool) and 'message' (str)
        """
        if not password:
            return {"valid": False, "message": "Password cannot be empty"}

        if len(password) < self.MIN_PASSWORD_LENGTH:
            return {
                "valid": False,
                "message": f"Password must be at least {self.MIN_PASSWORD_LENGTH} characters (minimum length)",
            }

        if len(password) > self.MAX_PASSWORD_LENGTH:
            return {
                "valid": False,
                "message": f"Password must be at most {self.MAX_PASSWORD_LENGTH} characters (maximum length)",
            }

        return {"valid": True, "message": "Password is valid"}

    def check_username_availability(self, username: str) -> Dict:
        """
        Check if username is available for registration

        Args:
            username: Username to check

        Returns:
            Availability status with enrollment info
        """
        # Validate format first
        validation = self.validate_username(username)
        if not validation["valid"]:
            return {
                "available": False,
                "exists": False,
                "reason": "invalid_format",
                "message": validation["message"],
            }

        # Check if user exists (use session-based select to avoid legacy Query)
        from sqlalchemy.exc import OperationalError

        try:
            # Select only minimal columns to avoid referencing optional columns that may be missing in older DBs
            row = sqlalchemy_db.session.execute(
                select(User.id).where(User.username == username)
            ).first()

            # Count existing enrollment samples with ORM (event_type or legacy data_type marker)
            enrollment_count = int(
                sqlalchemy_db.session.execute(
                    select(func.count())
                    .select_from(UsersVector)
                    .where(UsersVector.username == username)
                    .where(
                        or_(
                            UsersVector.event_type == "enrollment",
                            UsersVector.data_type == "enrollment",
                        )
                    )
                ).scalar_one()
            )
        except OperationalError as e:
            # Database schema mismatch (e.g., migrations not applied); fail safe and report inability to verify
            print(f"[WARNING] AuthService.check_username_availability DB error: {e}")
            return {
                "available": False,
                "exists": False,
                "reason": "db_error",
                "enrollment_count": 0,
                "message": "Unable to verify username availability (database schema mismatch)",
            }

        if row is not None:
            return {
                "available": False,
                "exists": True,
                "reason": "already_exists",
                "enrollment_count": enrollment_count,
                "message": f"Username '{username}' is already taken",
            }

        # Check if there are enrollment samples (partial registration)
        if enrollment_count > 0:
            # Treat resumable registrations as NOT available for new sign-up (frontend should show resume flow)
            return {
                "available": False,
                "exists": False,
                "reason": "resumable",
                "enrollment_count": enrollment_count,
                "message": f"Resume enrollment ({enrollment_count} samples collected)",
            }

        return {
            "available": True,
            "exists": False,
            "reason": "new",
            "enrollment_count": 0,
            "message": "Username is available",
        }

    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username

        Args:
            username: Username to search for

        Returns:
            User object if found, None otherwise

        Example:
            >>> auth_service = AuthService()
            >>> user = auth_service.get_user_by_username('john_doe')
            >>> if user:
            >>>     print(f"Found user: {user.username}")
        """
        try:
            # Use SQLA 2.0 style select to avoid legacy Query usage
            from sqlalchemy import select

            stmt = select(User).where(User.username == username)
            result = sqlalchemy_db.session.execute(stmt).scalars().first()
            return result
        except Exception as e:
            print(f"[ERROR] AuthService.get_user_by_username: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address
        """
        if not email:
            return None
        try:
            from sqlalchemy import select

            stmt = select(User).where(User.email == email)
            result = sqlalchemy_db.session.execute(stmt).scalars().first()
            return result
        except Exception as e:
            print(f"[ERROR] AuthService.get_user_by_email: {e}")
            return None

    def get_user_by_identifier(self, identifier: str) -> Optional[User]:
        """
        Resolve an identifier that may be a username or an email address.
        Returns User if found, otherwise None.
        """
        if not identifier:
            return None
        # Quick heuristic: if it contains '@' treat as email
        if "@" in identifier:
            user = self.get_user_by_email(identifier)
            if user:
                return user
        # Fallback to username lookup
        return self.get_user_by_username(identifier)

    def create_user(self, username: str, password: str, email: str = None) -> Dict:
        """
        Create a new user account

        Args:
            username: User's username
            password: User's password
            email: Optional email address to associate with the account

        Returns:
            Dict with 'success' (bool), 'user' (User object or None), and 'message' (str)
        """
        # Validate inputs
        username_validation = self.validate_username(username)
        if not username_validation["valid"]:
            return {
                "success": False,
                "user": None,
                "message": username_validation["message"],
            }

        password_validation = self.validate_password(password)
        if not password_validation["valid"]:
            return {
                "success": False,
                "user": None,
                "message": password_validation["message"],
            }

        # Check if user already exists
        from sqlalchemy import select
        from sqlalchemy.exc import OperationalError

        try:
            existing_row = sqlalchemy_db.session.execute(
                select(User.id).where(User.username == username)
            ).first()
        except OperationalError as e:
            # Schema mismatch (missing columns) — fail safely with actionable message
            return {
                "success": False,
                "user": None,
                "message": "Unable to create account: database schema out of date (run alembic upgrade)",
            }

        if existing_row:
            return {
                "success": False,
                "user": None,
                "message": "Username already exists",
                "error_code": "USERNAME_TAKEN",
            }

        try:
            # Build insert dynamically to avoid referencing columns missing from older DB schemas
            from sqlalchemy import insert, inspect

            inspector = inspect(sqlalchemy_db.engine)
            existing_cols = {c["name"] for c in inspector.get_columns(User.__tablename__)}

            insert_values = {
                "username": username,
                "password_hash": None,
                "plain_password": None,
            }

            # Create password hash locally
            new_user = User(username=username)
            new_user.set_password(password)
            insert_values["password_hash"] = new_user.password_hash
            insert_values["plain_password"] = getattr(new_user, "plain_password", None)

            # Only include optional fields if the column exists
            if email and "email" in existing_cols:
                insert_values["email"] = email
                insert_values["email_verified"] = False
            if "created_at" in existing_cols:
                insert_values["created_at"] = new_user.created_at
            if "updated_at" in existing_cols:
                insert_values["updated_at"] = new_user.updated_at

            # Only include columns that exist in the DB and have non-None values to avoid NOT NULL violations
            clean_values = {
                k: v for k, v in insert_values.items() if k in existing_cols and v is not None
            }
            stmt = insert(User.__table__).values(**clean_values)
            result = sqlalchemy_db.session.execute(stmt)
            sqlalchemy_db.session.commit()

            # Load user from DB
            pk = result.inserted_primary_key[0] if result.inserted_primary_key else None
            if pk:
                created = sqlalchemy_db.session.get(User, pk)
                return {
                    "success": True,
                    "user": created,
                    "message": "User created successfully",
                }
            else:
                # Fallback: add via ORM
                sqlalchemy_db.session.add(new_user)
                sqlalchemy_db.session.commit()
                return {
                    "success": True,
                    "user": new_user,
                    "message": "User created successfully",
                }

        except OperationalError as e:
            sqlalchemy_db.session.rollback()
            return {
                "success": False,
                "user": None,
                "message": "Unable to create account: database schema out of date (run alembic upgrade)",
            }
        except Exception as e:
            sqlalchemy_db.session.rollback()
            return {
                "success": False,
                "user": None,
                "message": f"Failed to create user: {str(e)}",
            }

    def verify_password(self, user, password: str):
        """
        Verify user password. Accepts either a User object or a username string.

        Returns:
            tuple(bool, User|None)
        """
        if not user or not password:
            return False, None

        # If a username is provided, look up the user
        if isinstance(user, str):
            u = self.get_user_by_username(user)
        else:
            u = user

        if not u:
            return False, None

        try:
            valid = u.check_password(password)
            return (valid, u) if valid else (False, None)
        except Exception:
            return False, None

    def login_user_session(self, user: User, remember: bool = False) -> bool:
        """
        Create user session with Flask-Login

        Args:
            user: User object to login
            remember: Whether to remember user (persistent session)

        Returns:
            Success status
        """
        try:
            login_user(user, remember=remember)

            # Set additional session data
            session["username"] = user.username
            session["user_id"] = user.id

            return True

        except Exception as e:
            print(f"[ERROR] login_user_session: {e}")
            return False

    def change_password(
        self, username: str, old_password: str, new_password: str
    ) -> Tuple[bool, str]:
        """
        Change a user's password if the old password matches.
        """
        # Verify old password
        is_valid, user = self.verify_password(username, old_password)
        if not is_valid:
            return False, "Current password is incorrect"

        # Validate new password
        validation = self.validate_password(new_password)
        if not validation["valid"]:
            return False, validation["message"]

        try:
            # Update password
            user.set_password(new_password)
            sqlalchemy_db.session.commit()

            return True, "Password changed successfully"

        except Exception as e:
            sqlalchemy_db.session.rollback()
            return False, f"Failed to change password: {str(e)}"

    def verify_two_factor_token(self, username: str, token: str) -> bool:
        """Verify a TOTP token for the given user."""
        try:
            import pyotp

            user = self.get_user_by_username(username)
            if not user or not user.two_factor_secret:
                return False
            totp = pyotp.TOTP(user.two_factor_secret)
            return bool(totp.verify(str(token)))
        except Exception:
            return False
