"""
API Blueprint - RESTful API endpoints for biometric authentication
"""
from flask import Blueprint, request, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app import limiter  # Import rate limiter
from db import Database
from verifier import Verifier
from password_strength import calculate_password_strength, get_strength_label, get_strength_recommendations
from app.utils.keystroke_processor import process_web_events, assess_sample_quality
from app.models import User  # Import User model
from app.services import AuthService, BiometricService  # Import service layer
import time
from datetime import datetime
import traceback

api_bp = Blueprint('api', __name__)

# Initialize database and verifier (legacy - being phased out)
db_manager = Database()
verifier = Verifier()

# Initialize services (new architecture)
auth_service = AuthService()
biometric_service = BiometricService()

# ============================================================================
# USERNAME VALIDATION
# ============================================================================

@api_bp.route('/check_username', methods=['POST'])
@limiter.limit("10 per minute")  # Prevent username enumeration
def check_username():
    """
    Check username availability for registration or login
    Uses AuthService + BiometricService for validation
    """
    try:
        data = request.json
        username = data.get('username', '').strip()
        check_mode = data.get('mode', 'register')
        
        if not username:
            return jsonify({
                "status": "error",
                "message": "Username tidak boleh kosong",
                "exists": False,
                "enrollment_complete": False,
                "enrollment_count": 0
            }), 400
        
        # Use AuthService to check availability
        availability = auth_service.check_username_availability(username)
        
        # Get enrollment status from BiometricService
        enrollment_status = biometric_service.get_enrollment_status(username)
        enrollment_count = enrollment_status['count']
        
        login_ready = enrollment_status['ready_for_login']  # 10+ samples
        registration_complete = enrollment_status['enrolled']  # 3+ samples
        
        print(f"[CHECK USERNAME] User: {username}, Mode: {check_mode}")
        print(f"  - Exists: {availability['exists']}, Enrollment: {enrollment_count}")
        
        # LOGIN MODE
        if check_mode == 'login':
            if not availability['exists']:
                return jsonify({
                    "exists": False,
                    "can_login": False,
                    "enrollment_complete": False,
                    "enrollment_count": 0,
                    "message": f"User {username} tidak ditemukan"
                }), 200
            
            return jsonify({
                "exists": True,
                "can_login": login_ready,
                "enrollment_complete": login_ready,
                "enrollment_count": enrollment_count,
                "message": f"User {username} ditemukan" if login_ready else f"Enrollment belum lengkap ({enrollment_count}/20)"
            }), 200
        
        # REGISTER MODE - Use AuthService response
        response_data = {
            "status": "taken" if not availability['available'] else "available",
            "available": availability['available'],
            "exists": availability['exists'],
            "message": availability['message'],
            "enrollment_count": enrollment_count,
            "is_retry": enrollment_count > 0
        }
        
        # No need to send sample count details to frontend
        response_data['detail'] = ""
        
        return jsonify(response_data)
    
    except Exception as e:
        print(f"[ERROR] check_username: {e}")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================================
# REGISTRATION ENDPOINTS
# ============================================================================

@api_bp.route('/register_sample', methods=['POST'])
@limiter.limit("30 per minute")  # Rate limit: 30 enrollment samples per minute
def register_sample():
    """
    Register a single keystroke sample during enrollment
    """
    try:
        data = request.json
        username = data.get('username', '').strip()
        events = data.get('events')
        
        if not events or not username:
            return jsonify({"status": "error", "message": "Data tidak lengkap"}), 400
        
        # Validate username
        validation = auth_service.validate_username(username)
        if not validation['valid']:
            return jsonify({
                "status": "error",
                "message": validation['message']
            }), 400
        
        # Check enrollment status
        enrollment_status = biometric_service.get_enrollment_status(username)
        enrollment_count = enrollment_status['count']
        
        # Allow continuing enrollment up to 20 samples
        # Username availability was already validated at /check_username
        
        if enrollment_count > 0:
            print(f"[INFO] User '{username}' continuing registration (progress: {enrollment_count}/20)")
        
        # Process keystroke events
        result = process_web_events(events, username)
        
        if result['status'] == 'success':
            features = result['features']
            features['username'] = username
            features['data_type'] = 'enrollment'
            
            # Quality assessment
            quality = assess_sample_quality(features)
            features['quality_label'] = quality['quality_label']
            features['quality_score'] = quality['quality_score']
            
            # Password strength detection
            real_pass = result.get('real_password_string')
            password_hash = result.get('password_hash')
            
            if real_pass:
                strength_result = calculate_password_strength(real_pass)
                features['password_strength'] = strength_result['strength']
                features['password_score'] = strength_result['score']
                
                # Enforce minimum password strength (first sample only)
                if enrollment_count == 0 and strength_result['score'] < 2:
                    return jsonify({
                        "status": "error",
                        "message": "Password terlalu lemah",
                        "error_code": "WEAK_PASSWORD",
                        "strength": strength_result['strength']
                    }), 400
                
                # PASSWORD VALIDATION: Check if typed password matches master password
                if enrollment_count > 0:
                    # For subsequent samples (2-20), validate against existing password
                    user = auth_service.get_user_by_username(username)
                    if user:
                        # Check if password matches
                        if not user.check_password(real_pass):
                            return jsonify({
                                "status": "error",
                                "message": "Password salah",
                                "error_code": "PASSWORD_MISMATCH"
                            }), 400
                    else:
                        return jsonify({
                            "status": "error",
                            "message": "User tidak ditemukan"
                        }), 404
                
                # Save credentials using AuthService (first enrollment only)
                if enrollment_count == 0:
                    # Create user account with password
                    user_result = auth_service.create_user(username, real_pass)
                    if not user_result['success']:
                        return jsonify({
                            "status": "error",
                            "message": user_result['message']
                        }), 400
            else:
                features['password_strength'] = 'unknown'
                features['password_score'] = 0
            
            # Save enrollment data (legacy - will migrate to BiometricService)
            db_manager.save_data(features)
            
            # Get updated enrollment count
            new_status = biometric_service.get_enrollment_status(username)
            new_count = new_status['count']
            
            return jsonify({
                "status": "success",
                "message": f"Sampel {new_count}/20 berhasil disimpan",
                "progress": {
                    "current": new_count,
                    "target": 20,
                    "complete": new_status['ready_for_login']
                },
                "quality": quality,
                "password_strength": {
                    "strength": strength_result['strength'] if real_pass else 'unknown',
                    "score": strength_result['score'] if real_pass else 0,
                    "label": get_strength_label(strength_result) if real_pass else 'Unknown'
                }
            })
        else:
            return jsonify({"status": "error", "message": result['msg']}), 400
    
    except Exception as e:
        print(f"[ERROR] register_sample: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@api_bp.route('/pre_verify_password', methods=['POST'])
def pre_verify_password():
    """
    Pre-verify password before collection/verification mode
    """
    try:
        data = request.json
        username = data.get('username')
        raw_events = data.get('events')
        
        if not username or not raw_events:
            return jsonify({
                'valid': False,
                'message': 'Data tidak lengkap'
            }), 400
        
        # Get enrollment data
        enrollment_data = db_manager.get_enrollment_samples(username)
        if not enrollment_data or len(enrollment_data) == 0:
            return jsonify({
                'valid': False,
                'message': 'User belum registrasi'
            }), 404
        
        # Process events
        result = process_web_events(raw_events, username)
        if result['status'] != 'success':
            return jsonify({
                'valid': False,
                'message': 'Gagal memproses keystroke data'
            }), 400
        
        features = result['features']
        password_hash = result.get('password_hash', '')
        
        # Check security tier
        stored_hash = db_manager.get_password_hash(username)
        
        if stored_hash:
            # Modern security: Hash + Keystroke (STRICTER)
            print(f"[Pre-Verify] User '{username}' → Tier 2 (Hash + Keystroke)")
            
            if password_hash != stored_hash:
                return jsonify({
                    'valid': False,
                    'message': 'Password salah',
                    'reason': 'hash_mismatch'
                }), 403
            
            keystroke_threshold = 0.2  # Stricter for modern users
            tier_label = "Hash+Keystroke"
        else:
            # Legacy: Keystroke only (LOOSER)
            print(f"[Pre-Verify] User '{username}' → Tier 1 (Keystroke Only)")
            keystroke_threshold = 0.4  # Looser for legacy users
            tier_label = "Keystroke Only (LEGACY)"
        
        # Keystroke verification
        verifier_adaptive = Verifier(method='euclidean', threshold=keystroke_threshold)
        verification_result = verifier_adaptive.verify_user(features, enrollment_data)
        
        score = float(verification_result['score'])
        is_genuine = verification_result['result']
        
        print(f"[Pre-Verify] {tier_label} | Score: {score:.4f} | Result: {'PASS' if is_genuine else 'FAIL'}")
        
        if not is_genuine:
            return jsonify({
                'valid': False,
                'message': f'Ritme ketikan tidak cocok (score: {score:.3f})',
                'reason': 'keystroke_mismatch',
                'score': score,
                'threshold': keystroke_threshold,
                'security_tier': 'modern' if stored_hash else 'legacy'
            }), 403
        
        return jsonify({
            'valid': True,
            'message': 'Pre-verification berhasil',
            'score': score,
            'threshold': keystroke_threshold,
            'security_tier': 'modern' if stored_hash else 'legacy'
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Pre-verification: {e}")
        traceback.print_exc()
        return jsonify({
            'valid': False,
            'message': f'Server Error: {str(e)}'
        }), 500


# ============================================================================
# LOGIN/VERIFICATION ENDPOINTS
# ============================================================================

@api_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")  # Rate limit: 10 login attempts per minute
def login():
    """
    Unified login endpoint with comprehensive biometric verification
    """
    try:
        data = request.json
        username = data.get('username', '').strip()
        events = data.get('events')
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        # Validate input
        if not username or not events:
            return jsonify({
                'success': False,
                'message': 'Data tidak lengkap',
                'reason': 'invalid_input'
            }), 400
        
        # Rate limiting
        recent_failed = db_manager.get_failed_login_count_recent(username, minutes=15)
        if recent_failed >= 5:
            db_manager.log_failed_login(username, 'rate_limit_exceeded', ip_address, user_agent)
            return jsonify({
                'success': False,
                'message': 'Coba lagi nanti',
                'reason': 'rate_limit_exceeded'
            }), 429
        
        # Extract features
        result = process_web_events(events, username)
        if result['status'] == 'error':
            db_manager.log_failed_login(username, 'invalid_keystroke_data', ip_address, user_agent)
            return jsonify({
                'success': False,
                'message': 'Keystroke data tidak valid',
                'reason': 'invalid_data'
            }), 400
        
        features = result['features']
        
        # Check enrollment status via BiometricService
        enrollment_status = biometric_service.get_enrollment_status(username)
        enrollment_count = enrollment_status['count']
        
        if enrollment_count == 0:
            db_manager.log_failed_login(username, 'no_enrollment', ip_address, user_agent)
            return jsonify({
                'success': False,
                'message': 'User belum terdaftar',
                'reason': 'no_enrollment'
            }), 404
        
        if not enrollment_status['ready_for_login']:  # Less than 10 samples
            db_manager.log_failed_login(username, 'insufficient_enrollment', ip_address, user_agent)
            return jsonify({
                'success': False,
                'message': f'Enrollment belum lengkap ({enrollment_count}/20)',
                'reason': 'insufficient_enrollment'
            }), 400
        
        # Get User model instance
        user = User.query.filter_by(username=username).first()
        if not user:
            db_manager.log_failed_login(username, 'user_not_found', ip_address, user_agent)
            return jsonify({
                'success': False,
                'message': 'User tidak ditemukan',
                'reason': 'user_not_found'
            }), 404
        
        # Pre-verification: Password hash check via AuthService
        input_hash = result.get('password_hash')
        real_password = result.get('real_password_string')
        
        # Verify password (supports both bcrypt and legacy)
        password_verified = auth_service.verify_password(user, real_password) if real_password else False
        
        if not password_verified:
            db_manager.log_failed_login(username, 'wrong_password_hash', ip_address, user_agent, score=1.0)
            return jsonify({
                'success': False,
                'message': 'Password salah',
                'reason': 'wrong_password'
            }), 403
        
        # Comprehensive keystroke verification via BiometricService
        verification_result = biometric_service.verify_keystroke_sample(username, features)
        
        if not verification_result.get('success'):
            db_manager.log_failed_login(username, 'verification_error', ip_address, user_agent)
            return jsonify({
                'success': False,
                'message': verification_result.get('message', 'Verification error'),
                'reason': 'verification_error'
            }), 500
        
        is_genuine = verification_result['verified']
        confidence_score = verification_result['score']
        
        # Decision logic
        if is_genuine:
            # Save verified login
            db_manager.save_verified_login({
                'username': username,
                'password_hash': user.password_hash,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'H_vector': features.get('H_vector'),
                'DD_vector': features.get('DD_vector'),
                'UD_vector': features.get('UD_vector'),
                'verification_score': confidence_score,
                'recommended_method': verification_result.get('confidence', 'medium'),
                'ip_address': ip_address,
                'user_agent': user_agent
            })
            
            # Use AuthService to create session (Flask-Login only)
            login_result = auth_service.login_user_session(user)
            if not login_result:
                return jsonify({
                    'success': False,
                    'message': 'Failed to create session',
                    'reason': 'session_error'
                }), 500
            
            return jsonify({
                'success': True,
                'message': 'Login berhasil',
                'score': confidence_score,
                'confidence_label': verification_result['confidence'],
                'templates_used': verification_result.get('templates_used', 0)
            }), 200
        
        else:
            # Log failed login
            db_manager.log_failed_login(
                username, 
                'impostor_detected', 
                ip_address, 
                user_agent, 
                score=confidence_score
            )
            
            return jsonify({
                'success': False,
                'message': 'Login gagal',
                'reason': 'impostor_detected',
                'score': confidence_score,
                'confidence_label': verification_result['confidence']
            }), 403
    
    except Exception as e:
        print(f"[ERROR] Login failed: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Server Error: {str(e)}',
            'reason': 'server_error'
        }), 500


@api_bp.route('/verify_user', methods=['POST'])
def verify_user():
    """
    Verify user with comprehensive biometric analysis
    """
    try:
        data = request.json
        username = data.get('username')
        events = data.get('events')
        
        if not events or not username:
            return jsonify({"message": "Data tidak lengkap"}), 400
        
        # Process events
        process_result = process_web_events(events, username)
        if process_result['status'] == 'error':
            return jsonify({"status": "error", "message": process_result['msg']}), 400
        
        new_features = process_result['features']
        
        # Get enrollment data
        enrollment_data = db_manager.get_enrollment_samples(username)
        
        if len(enrollment_data) < 5:
            return jsonify({
                "status": "error",
                "message": f"User belum terdaftar atau data enrollment kurang ({len(enrollment_data)} sampel)"
            }), 404
        
        # Comprehensive verification
        verification_result = verifier.verify_user_comprehensive(new_features, enrollment_data)
        
        # Log results
        new_features['username'] = username
        new_features['login_result'] = str(verification_result['final_decision'])
        new_features['login_score'] = verification_result['final_score']
        new_features['data_type'] = 'verification'
        db_manager.save_data(new_features)
        
        if verification_result['final_decision']:
            return jsonify({
                "status": "success",
                "message": "✅ Autentikasi berhasil!",
                "result": True,
                "score": verification_result['final_score'],
                "comprehensive": verification_result
            })
        else:
            return jsonify({
                "status": "fail",
                "message": "❌ Autentikasi gagal",
                "result": False,
                "score": verification_result['final_score'],
                "comprehensive": verification_result
            })
    
    except Exception as e:
        print(f"[ERROR] verify_user: {e}")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@api_bp.route('/user/info', methods=['GET'])
@login_required  # Flask-Login protection
def get_user_info():
    """
    Get current user information
    Uses BiometricService to get enrollment status
    """
    try:
        username = current_user.username  # Use Flask-Login current_user
        user_data = db_manager.get_user_by_username(username)
        
        if not user_data:
            return jsonify({
                "error": "User not found"
            }), 404
        
        # Use BiometricService for enrollment status
        enrollment_status = biometric_service.get_enrollment_status(username)
        verified_logins = db_manager.get_verified_login_count(username)
        
        return jsonify({
            "username": username,
            "email": user_data.get('email', 'N/A'),
            "last_login": user_data.get('last_login'),
            "session_start": session.get('login_time'),
            "enrollment_count": enrollment_status['count'],
            "enrollment_ready": enrollment_status['ready_for_login'],
            "verified_logins": verified_logins
        }), 200
    
    except Exception as e:
        print(f"[ERROR] get_user_info: {e}")
        traceback.print_exc()
        return jsonify({
            "error": str(e)
        }), 500


@api_bp.route('/user/reset_password', methods=['POST'])
@login_required  # Flask-Login protection
@limiter.limit("3 per hour")  # Rate limit: 3 password resets per hour
def reset_password():
    """
    Reset user password using AuthService
    """
    try:
        data = request.json
        new_password = data.get('new_password')
        username = current_user.username  # Use Flask-Login current_user
        
        if not new_password:
            return jsonify({
                "error": "New password required"
            }), 400
        
        # Use AuthService to change password
        result = auth_service.change_password(current_user, new_password)
        
        if not result['success']:
            return jsonify({
                "error": result['message']
            }), 400
        db_manager.delete_enrollment_data(username)
        
        # Logout user after password reset
        logout_user()
        session.clear()
        
        return jsonify({
            "success": True,
            "message": "Password reset successful. Please login again."
        }), 200
    
    except Exception as e:
        print(f"[ERROR] reset_password: {e}")
        traceback.print_exc()
        return jsonify({
            "error": str(e)
        }), 500


# ============================================================================
# DEBUG ENDPOINTS (Development only)
# ============================================================================

@api_bp.route('/debug/user/<username>', methods=['GET'])
def debug_user(username):
    """
    Debug endpoint to view user enrollment data
    """
    # Implementation will be migrated from original app.py
    return jsonify({
        "status": "error",
        "message": "Endpoint under migration"
    }), 501
