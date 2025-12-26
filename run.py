"""
Application entry point using Factory Pattern
"""
import os
import shutil
from pathlib import Path
from app import create_app

def clean_cache():
    """Remove Python cache files and directories"""
    print("Cleaning Python cache...")
    cache_dirs = [
        '__pycache__',
        'app/__pycache__',
        'app/blueprints/__pycache__',
        'app/models/__pycache__',
        'app/services/__pycache__',
        'app/utils/__pycache__',
        'tests/__pycache__'
    ]
    
    cleaned = 0
    for cache_dir in cache_dirs:
        cache_path = Path(cache_dir)
        if cache_path.exists():
            try:
                shutil.rmtree(cache_path)
                print(f"  Removed: {cache_dir}")
                cleaned += 1
            except Exception as e:
                print(f"  Failed to remove {cache_dir}: {e}")
    
    # Also remove .pyc files
    for pyc_file in Path('.').rglob('*.pyc'):
        try:
            pyc_file.unlink()
            cleaned += 1
        except Exception:
            pass
    
    if cleaned > 0:
        print(f"Cache cleaned: {cleaned} items removed\n")
    else:
        print("No cache found\n")

# Get configuration from environment variable or default to development
config_name = os.getenv('FLASK_ENV', 'development')

# Clean cache before starting
clean_cache()

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
