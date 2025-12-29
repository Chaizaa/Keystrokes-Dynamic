"""
Login Attempt Model - Track authentication attempts
"""
from datetime import datetime, timezone
from . import db


class LoginAttempt(db.Model):
    """
    Login attempt tracking for security and analytics
    
    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        username: Username attempted (denormalized)
        success: Whether login succeeded
        verification_score: Biometric verification score
        verification_method: Method used ('password_only', 'biometric', 'hybrid')
        failure_reason: Reason for failure if unsuccessful
        ip_address: Client IP address
        user_agent: Client user agent
        timestamp: Attempt timestamp
    """
    __tablename__ = 'login_attempts'
    
    # Composite indexes for common query patterns
    __table_args__ = (
        db.Index('idx_login_username_timestamp', 'username', 'timestamp'),
        db.Index('idx_login_username_success', 'username', 'success'),
        db.Index('idx_login_user_timestamp', 'user_id', 'timestamp'),
        db.Index('idx_login_ip_timestamp', 'ip_address', 'timestamp'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    username = db.Column(db.String(80), nullable=False, index=True)
    
    # Attempt result
    success = db.Column(db.Boolean, default=False, nullable=False, index=True)
    failure_reason = db.Column(db.String(255), nullable=True)
    
    # Biometric verification
    verification_score = db.Column(db.Float, nullable=True)
    verification_method = db.Column(db.String(50), nullable=True)  # 'password_only', 'biometric', 'hybrid'
    biometric_tier = db.Column(db.String(50), nullable=True)  # 'tier1', 'tier2', 'tier3'
    
    # Security tracking
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 support
    user_agent = db.Column(db.String(255), nullable=True)
    
    # Metadata
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    session_id = db.Column(db.String(100), nullable=True)
    
    # Rate limiting context
    attempts_in_window = db.Column(db.Integer, nullable=True)
    rate_limit_hit = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        status = "✅" if self.success else "❌"
        return f'<LoginAttempt {status} {self.username} @ {self.timestamp}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'username': self.username,
            'success': self.success,
            'failure_reason': self.failure_reason,
            'verification_score': self.verification_score,
            'verification_method': self.verification_method,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'ip_address': self.ip_address
        }
    
    @classmethod
    def get_recent_failed_attempts(cls, username, minutes=15):
        """
        Get recent failed login attempts for a username
        
        Args:
            username: Username to check
            minutes: Time window in minutes
            
        Returns:
            int: Number of failed attempts in time window
        """
        from datetime import timedelta
        threshold = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        
        from sqlalchemy import select, func
        return int(db.session.execute(
            select(func.count()).select_from(cls).where(
                cls.username == username,
                cls.success == False,
                cls.timestamp >= threshold
            )
        ).scalar_one())
    
    @classmethod
    def log_attempt(cls, username, success, **kwargs):
        """
        Log a login attempt
        
        Args:
            username: Username attempted
            success: Whether attempt succeeded
            **kwargs: Additional fields (verification_score, ip_address, etc.)
            
        Returns:
            LoginAttempt: Created attempt object
        """
        attempt = cls(
            username=username,
            success=success,
            **kwargs
        )
        db.session.add(attempt)
        db.session.commit()
        return attempt
