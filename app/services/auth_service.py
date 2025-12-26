"""
Authentication Service - User authentication and registration logic
Handles password validation, user creation, and login verification
"""
import hashlib
from typing import Dict, Optional, Tuple
from flask import session
from flask_login import login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from db import Database
from app.models import User, db as sqlalchemy_db


class AuthService:
    """
    Service class for authentication operations
    Handles user registration, login, and password management
    """
    
    def __init__(self):
        """Initialize authentication service with database connection"""
        self.db = Database()  # Legacy database manager
        
        # Password requirements
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
            return {'valid': False, 'message': "Username cannot be empty"}
        
        if len(username) < self.MIN_USERNAME_LENGTH:
            return {'valid': False, 'message': f"Username must be at least {self.MIN_USERNAME_LENGTH} characters"}
        
        if len(username) > self.MAX_USERNAME_LENGTH:
            return {'valid': False, 'message': f"Username must be less than {self.MAX_USERNAME_LENGTH} characters"}
        
        # Check alphanumeric
        if not username.replace('_', '').replace('-', '').isalnum():
            return {'valid': False, 'message': "Username can only contain letters, numbers, hyphens, and underscores"}
        
        return {'valid': True, 'message': "Username is valid"}
    
    def validate_password(self, password: str) -> Dict:
        """
        Validate password strength
        
        Args:
            password: Password to validate
            
        Returns:
            Dict with 'valid' (bool) and 'message' (str)
        """
        if not password:
            return {'valid': False, 'message': "Password cannot be empty"}
        
        if len(password) < self.MIN_PASSWORD_LENGTH:
            return {'valid': False, 'message': f"Password must be at least {self.MIN_PASSWORD_LENGTH} character"}
        
        if len(password) > self.MAX_PASSWORD_LENGTH:
            return {'valid': False, 'message': f"Password must be at most {self.MAX_PASSWORD_LENGTH} characters"}
        
        return {'valid': True, 'message': "Password is valid"}
    
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
        if not validation['valid']:
            return {
                'available': False,
                'exists': False,
                'reason': 'invalid_format',
                'message': validation['message']
            }
        
        # Check if user exists
        user = User.query.filter_by(username=username).first()
        enrollment_count = self.db.get_enrollment_count(username)
        
        if user:
            return {
                'available': False,
                'exists': True,
                'reason': 'already_exists',
                'enrollment_count': enrollment_count,
                'message': f"Username '{username}' is already taken"
            }
        
        # Check if there are enrollment samples (partial registration)
        if enrollment_count > 0:
            return {
                'available': True,
                'exists': False,
                'reason': 'resumable',
                'enrollment_count': enrollment_count,
                'message': f"Resume enrollment ({enrollment_count} samples collected)"
            }
        
        return {
            'available': True,
            'exists': False,
            'reason': 'new',
            'enrollment_count': 0,
            'message': "Username is available"
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
            return User.query.filter_by(username=username).first()
        except Exception as e:
            print(f"[ERROR] AuthService.get_user_by_username: {e}")
            return None
    
    def create_user(self, username: str, password: str) -> Dict:
        """
        Create a new user account
        
        Args:
            username: User's username
            password: User's password
            
        Returns:
            Dict with 'success' (bool), 'user' (User object or None), and 'message' (str)
        """
        # Validate inputs
        username_validation = self.validate_username(username)
        if not username_validation['valid']:
            return {'success': False, 'user': None, 'message': username_validation['message']}
        
        password_validation = self.validate_password(password)
        if not password_validation['valid']:
            return {'success': False, 'user': None, 'message': password_validation['message']}
        
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return {'success': False, 'user': None, 'message': "Username already exists"}
        
        try:
            # Create new user
            new_user = User(username=username)
            new_user.set_password(password)  # Hash password with bcrypt
            
            # Save to database
            sqlalchemy_db.session.add(new_user)
            sqlalchemy_db.session.commit()
            
            return {'success': True, 'user': new_user, 'message': "User created successfully"}
            
        except Exception as e:
            sqlalchemy_db.session.rollback()
            return {'success': False, 'user': None, 'message': f"Failed to create user: {str(e)}"}
    
    def verify_password(self, user: User, password: str) -> bool:
        """
        Verify user password
        
        Args:
            user: User object to verify
            password: Password to verify
            
        Returns:
            Boolean indicating if password is valid
        """
        if not user or not password:
            return False
        
        # Check password (supports both bcrypt hash and legacy plain password)
        return user.check_password(password)
    
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
            session['username'] = user.username
            session['user_id'] = user.id
            
            return True
            
        except Exception as e:
            print(f"[ERROR] login_user_session: {e}")
            return False
    
    def logout_user_session(self) -> bool:
        """
        Logout user and clear session
        
        Returns:
            Success status
        """
        try:
            logout_user()
            session.clear()
            return True
            
        except Exception as e:
            print(f"[ERROR] logout_user_session: {e}")
            return False
    
    def change_password(
        self,
        username: str,
        old_password: str,
        new_password: str
    ) -> Tuple[bool, str]:
        """
        Change user password
        
        Args:
            username: User's username
            old_password: Current password
            new_password: New password
            
        Returns:
            Tuple of (success, message)
        """
        # Verify old password
        is_valid, user = self.verify_password(username, old_password)
        if not is_valid:
            return False, "Current password is incorrect"
        
        # Validate new password
        validation = self.validate_password(new_password)
        if not validation['valid']:
            return False, validation['message']
        
        try:
            # Update password
            user.set_password(new_password)
            sqlalchemy_db.session.commit()
            
            return True, "Password changed successfully"
            
        except Exception as e:
            sqlalchemy_db.session.rollback()
            return False, f"Failed to change password: {str(e)}"
