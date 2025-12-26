# Keystroke Dynamics - Blueprint Architecture

## 🏗️ Struktur Aplikasi (Refactored)

### Direktori Utama

```
Keystrokes-Dynamic/             # Root directory
├── app/                          # Application package
│   ├── __init__.py              # Application factory
│   ├── blueprints/              # Modular route handlers
│   │   ├── __init__.py
│   │   ├── main.py             # Landing & dashboard
│   │   ├── auth.py             # Authentication routes
│   │   └── api.py              # API endpoints
│   └── utils/                   # Business logic utilities
│       ├── __init__.py
│       └── keystroke_processor.py  # Feature extraction
│
├── static/                      # Frontend assets
│   ├── css/
│   │   ├── base.css            # Core styles
│   │   ├── landing.css         # Landing page
│   │   ├── auth.css            # Login/register
│   │   └── dashboard.css       # Dashboard
│   └── js/
│       ├── keystroke.js        # Keystroke capture
│       └── validation.js       # Form validation
│
├── templates/                   # HTML templates
│   ├── base.html               # Base template (DRY)
│   ├── landing.html            # Landing page
│   ├── login_unified.html      # Login page
│   ├── register.html           # Registration page
│   └── dashboard.html          # User dashboard
│
├── config.py                    # Configuration management
├── run.py                       # Application entry point
├── db.py                        # Database manager
├── verifier.py                  # Biometric verification
├── password_strength.py         # Password strength checker
├── requirements.txt             # Dependencies
├── .env                         # Environment variables
│
└── app.py.bak                   # BACKUP (original monolithic)
```

## 🚀 Menjalankan Aplikasi

### Mode Development (Blueprint Architecture)
```bash
# Aktifkan virtual environment
venv\Scripts\activate

# Jalankan aplikasi baru dengan Blueprint
python run.py
```

### Mode Production
```bash
# Set environment
set FLASK_ENV=production

# Run dengan production config
python run.py
```

### Legacy Mode (Jika Diperlukan)
```bash
# Jalankan app.py original
python app.py
```

## 📋 API Endpoints

### Authentication
- `GET /` - Landing page
- `GET /home` - Dashboard (requires login)
- `GET /login` - Login page
- `GET /register` - Registration page
- `GET /logout` - Logout & clear session

### API (Prefix: /api)
- `POST /api/check_username` - Check username availability
- `POST /api/register_sample` - Register enrollment sample
- `POST /api/pre_verify_password` - Pre-verify password
- `POST /api/login` - Unified login with verification
- `POST /api/verify_user` - Comprehensive verification
- `GET /api/user/info` - Get user information
- `POST /api/user/reset_password` - Reset password

## 🔧 Configuration

### Environment Variables (.env)
```env
# Flask Settings
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Database
DATABASE_TYPE=sqlite
DATABASE_PATH=biometric_auth.db

# Security
SESSION_COOKIE_SECURE=True
SESSION_LIFETIME=3600

# ML Settings
ENROLLMENT_SAMPLES=20
VERIFICATION_THRESHOLD=0.3
MAX_FAILED_ATTEMPTS=5
```

### Configuration Classes (config.py)
- `DevelopmentConfig` - DEBUG=True, development settings
- `ProductionConfig` - Secure cookies, enforced SECRET_KEY
- `TestingConfig` - In-memory database, disabled CSRF

## 🎨 Design Philosophy

### "Less AI" Aesthetic
- **Natural spacing**: 17px, 26px, 32px, 52px (not perfect multiples)
- **Sophisticated colors**: #9ca8b8, #b8c5d6, #7a8a9a
- **Varied opacity**: 0.04, 0.08, 0.12, 0.25, 0.35
- **Asymmetric padding**: 52px 46px (hand-crafted feel)
- **No emojis** in professional contexts

### Code Organization
- **DRY Principle**: Template inheritance with base.html
- **Separation of Concerns**: Blueprints for routing, utils for business logic
- **Modular CSS**: Page-specific stylesheets extending base.css
- **Reusable JS**: Classes for keystroke capture and validation

## 📦 Dependencies

```txt
Flask==3.0.0
flask-cors==4.0.0
python-dotenv==1.0.0
```

## 🔄 Migration Status

### ✅ Completed
- [x] CSS extraction to static/css (4 files)
- [x] JavaScript modularization (2 files)
- [x] Base template system (Jinja2 inheritance)
- [x] Environment configuration (config.py + .env)
- [x] Blueprint architecture (main, auth, api)
- [x] Core API endpoints migration
- [x] Keystroke processing utilities

### 🚧 In Progress
- [ ] Test new Blueprint application
- [ ] Fix template references and imports
- [ ] Organize files (cleanup unused)

### 📝 Pending
- [ ] Migrate db.py to SQLAlchemy ORM
- [ ] Add unit tests for blueprints
- [ ] Add integration tests
- [ ] Performance optimization

## 🛠️ Development Notes

### Blueprint Pattern Benefits
1. **Scalability**: Easy to add new feature modules
2. **Maintainability**: Clear separation of concerns
3. **Testability**: Each blueprint can be tested independently
4. **Team Collaboration**: Multiple developers can work on different blueprints

### Application Factory Pattern
- Enables multiple app instances (testing, production)
- Cleaner dependency injection
- Better configuration management
- Easier to scale and extend

## 📝 Changelog

### Version 2.0.0 (Dec 24, 2025)
- Restructured to Blueprint architecture
- Added application factory pattern
- Extracted CSS to modular files
- Created reusable JavaScript modules
- Implemented configuration management
- Improved code organization and maintainability

### Version 1.0.0 (Original)
- Monolithic app.py structure
- Inline CSS in templates
- Inline JavaScript in templates
- No configuration management
