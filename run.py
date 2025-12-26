"""
Application entry point using Factory Pattern
"""
import os
from app import create_app

# Get configuration from environment variable or default to development
config_name = os.getenv('FLASK_ENV', 'development')

# Create application instance
app = create_app(config_name)

if __name__ == '__main__':
    # Get port from environment or default to 5000
    port = int(os.getenv('PORT', 5000))
    
    # Run application
    app.run(
        host='0.0.0.0',
        port=port,
        debug=app.config.get('DEBUG', False)
    )
