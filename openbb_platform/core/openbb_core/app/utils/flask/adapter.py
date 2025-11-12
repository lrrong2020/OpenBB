"""Flask-to-OpenBB conversion logic."""

from typing import Any
from openbb_core.app.router import Router

def is_flask_available() -> bool:
    """Check if Flask is available."""
    try:
        import flask
        return True
    except ImportError:
        return False

def create_flask_router(flask_app: Any) -> Router:
    """Create OpenBB router from Flask app - Phase 1 minimal implementation."""
    if not is_flask_available():
        raise ImportError("Flask is not available")
    
    router = Router(prefix="/flask")
    
    # Phase 2: Add route introspection and conversion
    
    return router