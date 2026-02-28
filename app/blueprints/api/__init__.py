"""
api blueprint package
=====================

Imports all route sub-modules so that their ``@api_bp.route`` decorators
are executed and the routes are registered on *api_bp*.

Usage (in app/__init__.py)::

    from app.blueprints.api import api_bp as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix="/api")
"""

from ._shared import api_bp  # noqa: F401 – re-exported for app/__init__.py

# Import order is irrelevant; all modules decorate the same api_bp object.
from . import enrollment  # noqa: F401
from . import login       # noqa: F401
from . import two_factor  # noqa: F401
from . import user        # noqa: F401
from . import verification  # noqa: F401
from . import dataset       # noqa: F401
