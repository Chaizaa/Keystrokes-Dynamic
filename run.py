"""
Application entry point using Factory Pattern
"""

import logging
import os
import shutil
from pathlib import Path

from app import create_app

# Configure basic logging for the entrypoint
logging.basicConfig(level=logging.INFO)


def clean_cache():
    """Remove Python cache files and directories"""
    logger = logging.getLogger(__name__)
    logger.info("Cleaning Python cache...")

    cleaned = 0

    # Remove any __pycache__ directories recursively
    for cache_path in Path(".").rglob("__pycache__"):
        try:
            shutil.rmtree(cache_path)
            logger.info(f"  Removed: {cache_path}")
            cleaned += 1
        except Exception as e:
            logger.warning(f"  Failed to remove {cache_path}: {e}")

    # Also remove standalone .pyc files
    for pyc_file in Path(".").rglob("*.pyc"):
        try:
            pyc_file.unlink()
            cleaned += 1
        except Exception as e:
            logger.warning(f"  Failed to remove {pyc_file}: {e}")

    if cleaned > 0:
        logger.info(f"Cache cleaned: {cleaned} items removed")
    else:
        logger.info("No cache found")


# Get configuration from environment variable or default to development
config_name = os.getenv("FLASK_ENV", "development")

# Create application instance
app = create_app(config_name)

if __name__ == "__main__":
    # Optionally clean cache (default enabled). Set CLEAN_CACHE=0 to disable.
    if os.getenv("CLEAN_CACHE", "1") == "1":
        clean_cache()

    # Get port from environment or default to 5000
    port = int(os.getenv("PORT", 5000))

    # Run application
    app.run(host="0.0.0.0", port=port, debug=app.config.get("DEBUG", False))
