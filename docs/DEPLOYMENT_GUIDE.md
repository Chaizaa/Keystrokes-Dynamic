# Deployment Guide
**Keystrokes-Dynamic Biometric Authentication System**  
**Production Deployment Manual**

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Production Configuration](#production-configuration)
3. [Database Setup](#database-setup)
4. [Web Server Configuration](#web-server-configuration)
5. [Security Hardening](#security-hardening)
6. [Monitoring & Logging](#monitoring--logging)
7. [Backup & Recovery](#backup--recovery)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum**:
- CPU: 2 cores
- RAM: 2GB
- Disk: 10GB SSD
- OS: Ubuntu 20.04 LTS / Windows Server 2019

**Recommended (Production)**:
- CPU: 4 cores
- RAM: 8GB
- Disk: 50GB SSD
- OS: Ubuntu 22.04 LTS

### Software Requirements

```bash
# Python 3.12+
python3 --version

# PostgreSQL 14+ (Production) or SQLite 3.35+ (Development)
psql --version

# Nginx 1.18+ or Apache 2.4+
nginx -v

# Git 2.30+
git --version
```

---

## Production Configuration

### 1. Clone Repository

```bash
# Create application directory
sudo mkdir -p /var/www/keystroke-auth
cd /var/www/keystroke-auth

# Clone repository
git clone https://github.com/Chaizaa/Keystrokes-Dynamic.git .

# Set ownership
sudo chown -R www-data:www-data /var/www/keystroke-auth
```

### 2. Virtual Environment Setup

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
.\venv\Scripts\activate  # Windows

# Upgrade pip
pip install --upgrade pip

# Install production dependencies
pip install -r requirements.txt

# Install production-only packages
pip install gunicorn psycopg2-binary
```

### 3. Environment Variables

Create `.env` file (never commit to git):

```bash
# Flask Configuration
FLASK_APP=app
FLASK_ENV=production
SECRET_KEY=your-super-secret-key-change-this-in-production

# Database Configuration (PostgreSQL)
DATABASE_URL=postgresql://username:password@localhost:5432/keystroke_db

# Security
SESSION_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
PERMANENT_SESSION_LIFETIME=3600

# Rate Limiting
RATELIMIT_STORAGE_URL=redis://localhost:6379/0
RATELIMIT_ENABLED=True

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/keystroke-auth/app.log

# Email (for notifications)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Application Settings
MAX_ENROLLMENT_SAMPLES=20
MIN_ENROLLMENT_SAMPLES=10
VERIFICATION_THRESHOLD=0.7
```

**Generate Secret Key**:
```python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Configuration File

Create `config.py` with production settings:

```python
import os
from datetime import timedelta

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Security Headers
    SECURITY_HEADERS = {
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
    }

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # PostgreSQL Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://keystroke_user:password@localhost/keystroke_db'
    
    # Rate Limiting
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL') or \
        'redis://localhost:6379/0'
    
    # Logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = '/var/log/keystroke-auth/app.log'

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dev_keystroke.db'
    SESSION_COOKIE_SECURE = False

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
```

---

## Database Setup

### PostgreSQL Installation & Configuration

#### Ubuntu/Debian

```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Access PostgreSQL
sudo -u postgres psql
```

#### Create Database & User

```sql
-- Create database
CREATE DATABASE keystroke_db;

-- Create user
CREATE USER keystroke_user WITH ENCRYPTED PASSWORD 'strong_password_here';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE keystroke_db TO keystroke_user;

-- Connect to database
\c keystroke_db

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO keystroke_user;

-- Exit
\q
```

### Database Migration

```bash
# Activate virtual environment
source venv/bin/activate

# Initialize migrations (first time only)
flask db init

# Create migration
flask db migrate -m "Initial production schema"

# Apply migration
flask db upgrade

# Verify tables created
flask shell
>>> from app import db
>>> db.engine.table_names()
```

> **Important:** After deploying new code that includes schema changes, **always** run the migrations in your target environment. You can run `alembic upgrade head` or `flask db upgrade`. Failure to run migrations may cause runtime errors (e.g., missing user columns for email/2FA). Consider adding an uptime check to poll `/health/migrations` and alert on a non-200 response (503 indicates migrations are out-of-date or the DB is unreachable).

### Database Backup Script

Create `/usr/local/bin/backup-keystroke-db.sh`:

```bash
#!/bin/bash
# Database backup script

BACKUP_DIR="/var/backups/keystroke-auth"
DB_NAME="keystroke_db"
DB_USER="keystroke_user"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${DATE}.sql.gz"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create backup
pg_dump -U $DB_USER $DB_NAME | gzip > $BACKUP_FILE

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"
```

Make executable and add to cron:

```bash
sudo chmod +x /usr/local/bin/backup-keystroke-db.sh

# Add to crontab (daily at 2 AM)
sudo crontab -e
0 2 * * * /usr/local/bin/backup-keystroke-db.sh
```

---

## Web Server Configuration

### Option 1: Gunicorn + Nginx (Recommended)

#### 1. Gunicorn Configuration

Create `/var/www/keystroke-auth/gunicorn_config.py`:

```python
import multiprocessing

# Server socket
bind = '127.0.0.1:8000'
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
timeout = 30
keepalive = 2

# Process naming
proc_name = 'keystroke-auth'

# Logging
accesslog = '/var/log/keystroke-auth/gunicorn-access.log'
errorlog = '/var/log/keystroke-auth/gunicorn-error.log'
loglevel = 'info'

# Security
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190
```

#### 2. Systemd Service

Create `/etc/systemd/system/keystroke-auth.service`:

```ini
[Unit]
Description=Gunicorn instance for Keystroke Authentication
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/keystroke-auth
Environment="PATH=/var/www/keystroke-auth/venv/bin"
EnvironmentFile=/var/www/keystroke-auth/.env
ExecStart=/var/www/keystroke-auth/venv/bin/gunicorn \
    --config /var/www/keystroke-auth/gunicorn_config.py \
    --env FLASK_ENV=production \
    'app:create_app()'
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Enable and start service:

```bash
# Create log directory
sudo mkdir -p /var/log/keystroke-auth
sudo chown www-data:www-data /var/log/keystroke-auth

# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable keystroke-auth

# Start service
sudo systemctl start keystroke-auth

# Check status
sudo systemctl status keystroke-auth

# View logs
sudo journalctl -u keystroke-auth -f
```

#### 3. Nginx Configuration

Create `/etc/nginx/sites-available/keystroke-auth`:

```nginx
# Rate limiting zones
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;

# Upstream Gunicorn
upstream keystroke_app {
    server 127.0.0.1:8000 fail_timeout=0;
}

server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
    
    # Logging
    access_log /var/log/nginx/keystroke-auth-access.log;
    error_log /var/log/nginx/keystroke-auth-error.log;
    
    # Client body size limit
    client_max_body_size 1M;
    
    # Static files
    location /static {
        alias /var/www/keystroke-auth/app/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    # API endpoints with rate limiting
    location /api/verify {
        limit_req zone=login_limit burst=2 nodelay;
        
        proxy_pass http://keystroke_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
    
    location /api/ {
        limit_req zone=api_limit burst=5 nodelay;
        
        proxy_pass http://keystroke_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
    
    # Application routes
    location / {
        proxy_pass http://keystroke_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
}
```

Enable site and restart Nginx:

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/keystroke-auth /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

#### 4. SSL Certificate (Let's Encrypt)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# Auto-renewal (cron)
sudo certbot renew --dry-run

# Add to crontab
0 3 * * * certbot renew --quiet
```

---

### Option 2: Apache + mod_wsgi

#### 1. Install mod_wsgi

```bash
sudo apt install apache2 libapache2-mod-wsgi-py3
```

#### 2. Create WSGI File

Create `/var/www/keystroke-auth/wsgi.py`:

```python
import sys
import os

# Add application directory to path
sys.path.insert(0, '/var/www/keystroke-auth')

# Set environment variables
os.environ['FLASK_ENV'] = 'production'

from app import create_app

application = create_app('production')
```

#### 3. Apache Configuration

Create `/etc/apache2/sites-available/keystroke-auth.conf`:

```apache
<VirtualHost *:80>
    ServerName your-domain.com
    ServerAdmin admin@your-domain.com
    
    # Redirect to HTTPS
    Redirect permanent / https://your-domain.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName your-domain.com
    ServerAdmin admin@your-domain.com
    
    # SSL Configuration
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/your-domain.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/your-domain.com/privkey.pem
    
    # WSGI Configuration
    WSGIDaemonProcess keystroke_app python-home=/var/www/keystroke-auth/venv \
        python-path=/var/www/keystroke-auth \
        processes=4 threads=2 \
        display-name=%{GROUP}
    WSGIProcessGroup keystroke_app
    WSGIScriptAlias / /var/www/keystroke-auth/wsgi.py
    
    # Directory permissions
    <Directory /var/www/keystroke-auth>
        Require all granted
    </Directory>
    
    # Static files
    Alias /static /var/www/keystroke-auth/app/static
    <Directory /var/www/keystroke-auth/app/static>
        Require all granted
    </Directory>
    
    # Logging
    ErrorLog ${APACHE_LOG_DIR}/keystroke-auth-error.log
    CustomLog ${APACHE_LOG_DIR}/keystroke-auth-access.log combined
</VirtualHost>
```

Enable site:

```bash
# Enable modules
sudo a2enmod ssl wsgi rewrite headers

# Enable site
sudo a2ensite keystroke-auth

# Test configuration
sudo apache2ctl configtest

# Restart Apache
sudo systemctl restart apache2
```

---

## Security Hardening

### 1. Firewall Configuration (UFW)

```bash
# Enable UFW
sudo ufw enable

# Allow SSH
sudo ufw allow ssh

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow PostgreSQL (only from localhost)
sudo ufw allow from 127.0.0.1 to any port 5432

# Check status
sudo ufw status
```

### 2. Fail2Ban Configuration

```bash
# Install Fail2Ban
sudo apt install fail2ban

# Create jail configuration
sudo nano /etc/fail2ban/jail.local
```

Add configuration:

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true

[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/keystroke-auth-error.log

[keystroke-auth]
enabled = true
port = http,https
filter = keystroke-auth
logpath = /var/log/keystroke-auth/app.log
maxretry = 5
bantime = 3600
```

Create filter `/etc/fail2ban/filter.d/keystroke-auth.conf`:

```ini
[Definition]
failregex = ^.*Authentication failed.*from <HOST>.*$
            ^.*Invalid login attempt.*from <HOST>.*$
ignoreregex =
```

Restart Fail2Ban:

```bash
sudo systemctl restart fail2ban
sudo fail2ban-client status
```

### 3. PostgreSQL Security

Edit `/etc/postgresql/14/main/pg_hba.conf`:

```
# Local connections only
local   all             all                                     peer
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256
```

Edit `/etc/postgresql/14/main/postgresql.conf`:

```
listen_addresses = 'localhost'
max_connections = 100
shared_buffers = 256MB
```

Restart PostgreSQL:

```bash
sudo systemctl restart postgresql
```

### 4. File Permissions

```bash
# Set proper ownership
sudo chown -R www-data:www-data /var/www/keystroke-auth

# Restrict permissions
sudo find /var/www/keystroke-auth -type d -exec chmod 755 {} \;
sudo find /var/www/keystroke-auth -type f -exec chmod 644 {} \;

# Protect sensitive files
sudo chmod 600 /var/www/keystroke-auth/.env
sudo chmod 600 /var/www/keystroke-auth/config.py

# Restrict log directory
sudo chmod 750 /var/log/keystroke-auth
```

---

## Monitoring & Logging

### 1. Application Logging

Configure in `app/__init__.py`:

```python
import logging
from logging.handlers import RotatingFileHandler
import os

def configure_logging(app):
    """Configure application logging"""
    if not app.debug and not app.testing:
        # Create logs directory
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            'logs/keystroke_auth.log',
            maxBytes=10485760,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Keystroke Authentication startup')
```

### 2. System Monitoring (Optional - Prometheus)

Install Prometheus Flask exporter:

```bash
pip install prometheus-flask-exporter
```

Add to `app/__init__.py`:

```python
from prometheus_flask_exporter import PrometheusMetrics

def create_app(config_name='default'):
    app = Flask(__name__)
    
    # Prometheus metrics
    metrics = PrometheusMetrics(app)
    
    # Custom metrics
    metrics.info('app_info', 'Application info', version='2.0')
    
    return app
```

Access metrics at `http://your-domain.com/metrics`

### 3. Health Check Endpoint

Add to `app/blueprints/main.py`:

```python
@main_bp.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500
```

**Monitoring tip:** Add `/health/migrations` as an uptime check to verify that required DB migrations are applied. Alert when this endpoint returns a non-200 (it returns 503 when required user columns are missing or when the DB cannot be inspected). Optionally, poll `/admin/diagnostics` for richer information (alembic revision, available migration files, and user columns) and restrict access to that endpoint to trusted admin networks.

---

## Backup & Recovery

### 1. Automated Backup Script

Create `/usr/local/bin/full-backup.sh`:

```bash
#!/bin/bash
# Full system backup

BACKUP_ROOT="/var/backups/keystroke-auth"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/$DATE"

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
pg_dump -U keystroke_user keystroke_db | gzip > "$BACKUP_DIR/database.sql.gz"

# Application files backup
tar -czf "$BACKUP_DIR/application.tar.gz" \
    -C /var/www \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    keystroke-auth

# Configuration backup
tar -czf "$BACKUP_DIR/config.tar.gz" \
    /etc/nginx/sites-available/keystroke-auth \
    /etc/systemd/system/keystroke-auth.service \
    /var/www/keystroke-auth/.env

# Upload to S3 (optional)
# aws s3 cp $BACKUP_DIR s3://your-bucket/backups/ --recursive

# Keep only last 30 days
find $BACKUP_ROOT -type d -mtime +30 -exec rm -rf {} \;

echo "Backup completed: $BACKUP_DIR"
```

### 2. Recovery Procedure

```bash
# Stop application
sudo systemctl stop keystroke-auth

# Restore database
gunzip -c /var/backups/keystroke-auth/YYYYMMDD_HHMMSS/database.sql.gz | \
    psql -U keystroke_user keystroke_db

# Restore application files
tar -xzf /var/backups/keystroke-auth/YYYYMMDD_HHMMSS/application.tar.gz \
    -C /var/www

# Restore configuration
tar -xzf /var/backups/keystroke-auth/YYYYMMDD_HHMMSS/config.tar.gz -C /

# Set permissions
sudo chown -R www-data:www-data /var/www/keystroke-auth

# Start application
sudo systemctl start keystroke-auth
```

---

## Troubleshooting

### Common Issues

#### 1. Application Won't Start

```bash
# Check logs
sudo journalctl -u keystroke-auth -n 50

# Check Gunicorn errors
sudo tail -f /var/log/keystroke-auth/gunicorn-error.log

# Test configuration
python3 -c "from app import create_app; app = create_app('production'); print('OK')"
```

#### 2. Database Connection Errors

```bash
# Test PostgreSQL connection
psql -U keystroke_user -d keystroke_db -h localhost

# Check PostgreSQL status
sudo systemctl status postgresql

# View PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-14-main.log
```

#### 3. Nginx 502 Bad Gateway

```bash
# Check if Gunicorn is running
sudo systemctl status keystroke-auth

# Check Nginx error log
sudo tail -f /var/log/nginx/keystroke-auth-error.log

# Test upstream connection
curl http://127.0.0.1:8000
```

#### 4. SSL Certificate Issues

```bash
# Check certificate expiry
sudo certbot certificates

# Renew certificate
sudo certbot renew --force-renewal

# Test SSL configuration
openssl s_client -connect your-domain.com:443 -servername your-domain.com
```

### Performance Optimization

#### 1. PostgreSQL Tuning

Edit `/etc/postgresql/14/main/postgresql.conf`:

```
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 4MB
min_wal_size = 1GB
max_wal_size = 4GB
```

#### 2. Gunicorn Worker Tuning

```python
# gunicorn_config.py
import multiprocessing

workers = (2 * multiprocessing.cpu_count()) + 1
worker_class = 'gevent'  # For async I/O
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
```

#### 3. Redis Caching (Optional)

```bash
# Install Redis
sudo apt install redis-server

# Configure Flask-Caching
pip install Flask-Caching
```

Add to application:

```python
from flask_caching import Cache

cache = Cache(config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': 'redis://localhost:6379/1'
})
cache.init_app(app)
```

---

## Maintenance

### Regular Tasks

**Daily**:
- ✅ Check application logs for errors
- ✅ Monitor system resources (CPU, RAM, Disk)
- ✅ Verify automated backups completed

**Weekly**:
- ✅ Review security logs
- ✅ Check database size and performance
- ✅ Update dependencies if needed

**Monthly**:
- ✅ Test backup restoration
- ✅ Review and rotate logs
- ✅ Security audit
- ✅ Performance review

---

## Contact & Support

**Documentation**: [GitHub Repository](https://github.com/Chaizaa/Keystrokes-Dynamic)  
**Issues**: [GitHub Issues](https://github.com/Chaizaa/Keystrokes-Dynamic/issues)

---

**Last Updated**: December 24, 2024  
**Version**: 2.0  
**Status**: Production Ready ✅
