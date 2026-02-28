"""app.api — externally-facing API Blueprint with API-key authentication."""

from flask import Blueprint

api = Blueprint("client_api", __name__)

from .auth import require_api_key  # noqa: E402


@api.before_request
def _authenticate():
    """Require a valid API key before every route in this blueprint."""
    return require_api_key()


# Register routes
from . import routes  # noqa: E402, F401
