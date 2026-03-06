"""
API Key Service - Manage API key generation and validation
"""

from flask import current_app
from sqlalchemy import select

from app.models import db, APIKey, EnrollmentLog, VerificationLog


class APIKeyService:
    """Service for managing API keys"""

    @staticmethod
    def generate_new_key(user_id, partner_name, description=None, rate_limit=100, allowed_origins=None):
        """
        Generate and store a new API key
        
        Args:
            user_id: User ID of admin creating the key
            partner_name: Name of partner organization
            description: Optional description of the key
            rate_limit: Optional rate limit (default 100 requests/hour)
            allowed_origins: Optional comma-separated list of allowed domains
            
        Returns:
            tuple: (full_key, api_key_model) - full_key should be given to partner
        """
        # Generate key
        full_key, key_prefix, key_hash = APIKey.generate_key()
        
        # Create database record
        api_key = APIKey(
            user_id=user_id,
            partner_name=partner_name,
            description=description,
            key_prefix=key_prefix,
            key_hash=key_hash,
            rate_limit=rate_limit,
            allowed_origins=allowed_origins,
            is_active=True
        )
        
        db.session.add(api_key)
        db.session.commit()
        
        current_app.logger.info(f"Created API key {key_prefix} for partner {partner_name}")
        
        return full_key, api_key

    @staticmethod
    def verify_api_key(provided_key):
        """
        Verify if provided API key is valid and active
        
        Args:
            provided_key: The API key from request header
            
        Returns:
            tuple: (is_valid, api_key_model, error_message)
        """
        if not provided_key:
            return False, None, "Missing API key"

        # Accept either raw key or Authorization header value.
        candidate_key = provided_key.strip()
        if candidate_key.lower().startswith("bearer "):
            candidate_key = candidate_key.split(" ", 1)[1].strip()
        if not candidate_key:
            return False, None, "Missing API key"
        
        # Extract key prefix (first 20 chars)
        key_prefix = candidate_key[:20] if len(candidate_key) >= 20 else candidate_key[:10]
        
        # Find key by prefix (for efficiency)
        stmt = select(APIKey).where(
            APIKey.key_prefix == key_prefix,
            APIKey.is_active.is_(True)
        )
        api_key = db.session.execute(stmt).scalars().first()
        
        if not api_key:
            current_app.logger.warning(f"API key lookup failed for prefix: {key_prefix}")
            return False, None, "Invalid API key"
        
        # Check if expired
        if not api_key.is_valid():
            return False, None, "API key expired or inactive"
        
        # Verify hash
        if not api_key.check_key(candidate_key):
            current_app.logger.warning(f"API key hash mismatch for: {key_prefix}")
            return False, None, "Invalid API key"
        
        return True, api_key, None

    @staticmethod
    def check_rate_limit(api_key):
        """
        Check if API key has remaining quota
        
        Args:
            api_key: APIKey model instance
            
        Returns:
            tuple: (is_allowed, remaining_quota, error_message)
        """
        remaining = api_key.get_remaining_quota()
        
        if remaining <= 0:
            return False, 0, f"Rate limit exceeded. Limit: {api_key.rate_limit} per hour"
        
        return True, remaining, None

    @staticmethod
    def check_origin_allowed(api_key, origin):
        """
        Check if origin/domain is allowed for this API key
        
        Args:
            api_key: APIKey model instance
            origin: Origin header from request (e.g., "https://partner.com")
            
        Returns:
            bool: True if origin is allowed
        """
        if not api_key.allowed_origins:
            # If no origin restrictions, allow all
            return True
        
        allowed_list = [o.strip() for o in api_key.allowed_origins.split(",")]
        
        # Extract domain from origin URL if needed
        if origin and origin.startswith("http"):
            from urllib.parse import urlparse
            parsed = urlparse(origin)
            origin_domain = parsed.netloc
        else:
            origin_domain = origin
        
        return origin_domain in allowed_list

    @staticmethod
    def list_api_keys(user_id=None, partner_name=None, active_only=True):
        """
        List API keys with optional filters
        
        Args:
            user_id: Filter by creator user ID
            partner_name: Filter by partner name
            active_only: Only show active keys (default True)
            
        Returns:
            list: List of APIKey models
        """
        stmt = select(APIKey)
        
        if user_id:
            stmt = stmt.where(APIKey.user_id == user_id)
        
        if partner_name:
            stmt = stmt.where(APIKey.partner_name == partner_name)
        
        if active_only:
            stmt = stmt.where(APIKey.is_active.is_(True))
        
        stmt = stmt.order_by(APIKey.created_at.desc())
        
        return db.session.execute(stmt).scalars().all()

    @staticmethod
    def deactivate_key(api_key_id, user_id=None):
        """
        Deactivate an API key (safe delete)
        
        Args:
            api_key_id: ID of API key to deactivate
            user_id: Optional owner check. If provided, key must belong to this user.
            
        Returns:
            bool: True if successful
        """
        api_key = db.session.get(APIKey, api_key_id)
        if not api_key:
            return False

        if user_id is not None and api_key.user_id != user_id:
            return False
        
        api_key.is_active = False
        db.session.commit()
        
        current_app.logger.info(f"Deactivated API key: {api_key.key_prefix}")
        return True

    @staticmethod
    def log_enrollment(api_key_id, username, email, samples_count, client_ip=None):
        """
        Log an enrollment request
        
        Args:
            api_key_id: API key ID used
            username: Username being enrolled
            email: Email address
            samples_count: Number of keystroke samples
            client_ip: Client IP address
            
        Returns:
            EnrollmentLog: The created log entry
        """
        log = EnrollmentLog(
            api_key_id=api_key_id,
            username=username,
            email=email,
            samples_count=samples_count,
            client_ip=client_ip,
            status="pending"
        )
        db.session.add(log)
        db.session.commit()
        
        return log

    @staticmethod
    def log_verification(api_key_id, username, verified, confidence_score=None, error_message=None, client_ip=None):
        """
        Log a verification request
        
        Args:
            api_key_id: API key ID used
            username: Username being verified
            verified: Boolean - whether verification succeeded
            confidence_score: Float (0.0-1.0) - match confidence
            error_message: If verification failed, error details
            client_ip: Client IP address
            
        Returns:
            VerificationLog: The created log entry
        """
        log = VerificationLog(
            api_key_id=api_key_id,
            username=username,
            verified=verified,
            confidence_score=confidence_score,
            error_message=error_message,
            client_ip=client_ip
        )
        db.session.add(log)
        db.session.commit()
        
        return log

    @staticmethod
    def get_key_stats(api_key_id):
        """
        Get statistics for an API key
        
        Args:
            api_key_id: API key ID
            
        Returns:
            dict: Statistics including total enrollments, verifications, success rate
        """
        stats = {
            "total_enrollments": EnrollmentLog.query.filter_by(api_key_id=api_key_id).count(),
            "successful_enrollments": EnrollmentLog.query.filter_by(
                api_key_id=api_key_id, status="success"
            ).count(),
            "total_verifications": VerificationLog.query.filter_by(api_key_id=api_key_id).count(),
            "successful_verifications": VerificationLog.query.filter_by(
                api_key_id=api_key_id, verified=True
            ).count(),
        }
        
        # Calculate success rates
        if stats["total_enrollments"] > 0:
            stats["enrollment_success_rate"] = (
                stats["successful_enrollments"] / stats["total_enrollments"] * 100
            )
        else:
            stats["enrollment_success_rate"] = 0
        
        if stats["total_verifications"] > 0:
            stats["verification_success_rate"] = (
                stats["successful_verifications"] / stats["total_verifications"] * 100
            )
        else:
            stats["verification_success_rate"] = 0
        
        return stats
