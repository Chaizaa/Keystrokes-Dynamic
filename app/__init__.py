"""
Flask Application Factory with SQLAlchemy, Flask-Login, and Security Extensions
"""
from flask import Flask
from flask_cors import CORS
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_migrate import Migrate
import secrets


# Initialize extensions (without app)
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)
migrate = Migrate()


def create_app(config_name='development'):
    """
    Application factory pattern for Flask
    
    Args:
        config_name: Configuration environment (development/production/testing) or dict with config values
    
    Returns:
        Flask application instance
    """
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    # Load configuration
    import sys
    import os
    # Add parent directory to path so we can import config
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from config import get_config
    
    # Handle both string config name and dict config
    if isinstance(config_name, dict):
        app.config.update(config_name)
    else:
        app.config.from_object(get_config(config_name))
    
    # Set secret key for session management
    if not app.config.get('SECRET_KEY'):
        app.secret_key = secrets.token_hex(32)
    
    # CSRF Configuration - allow tokens from headers
    app.config['WTF_CSRF_CHECK_DEFAULT'] = True
    app.config['WTF_CSRF_HEADERS'] = ['X-CSRFToken', 'X-CSRF-Token']
    app.config['WTF_CSRF_TIME_LIMIT'] = None  # No expiration for development
    
    # Initialize database
    from app.models import db
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize extensions
    CORS(app)
    
    # Flask-Login configuration
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login_page'  # Redirect to login page
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return db.session.get(User, int(user_id))
    
    # CSRF Protection (exempt API routes)
    csrf.init_app(app)
    
    # Exempt API blueprint from CSRF (for AJAX/fetch requests)
    from app.blueprints.api import api_bp as api_blueprint
    csrf.exempt(api_blueprint)
    
    # Rate Limiting
    limiter.init_app(app)
    
    # Security Headers (only in production)
    if config_name == 'production':
        Talisman(app, 
                force_https=True,
                strict_transport_security=True,
                session_cookie_secure=True,
                content_security_policy={
                    'default-src': "'self'",
                    'script-src': ["'self'", "'unsafe-inline'"],
                    'style-src': ["'self'", "'unsafe-inline'"]
                })
    
    # Register blueprints
    from app.blueprints.main import main_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.api import api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app
