"""Flask Adapter Router for OpenBB Platform.

Implements Darren Lee's Phase 1 specification for Flask adapter integration.
"""

from openbb_core.app.router import Router
from .utils.adapter import FlaskAdapter

# Create base router for the extension
router = Router(prefix="/flask_adapter", description="Flask application adapter")

# Add Router.from_flask() class method
def from_flask(cls, flask_app, prefix: str = "/flask") -> "Router":
    """Create OpenBB Router from Flask application.
    
    Phase 1 Implementation: Entry Point
    - Mounts Flask app to OpenBB Router
    - Discovers and maps Flask routes
    - Provides foundation for Phase 2 Widget Factory
    
    Args:
        flask_app: Flask application instance
        prefix: URL prefix for mounted routes
        
    Returns:
        Router instance with Flask app mounted
        
    Example:
        >>> from flask import Flask
        >>> from openbb_core.app.router import Router
        >>> 
        >>> app = Flask(__name__)
        >>> @app.route('/test')
        >>> def test(): return {"message": "test"}
        >>> 
        >>> flask_router = Router.from_flask(app, prefix="/my_app")
    """
    # Validate Flask app without importing Flask
    if flask_app.__class__.__name__ != "Flask":
        raise TypeError(f"Expected Flask application, got {type(flask_app)}")
    
    # Create adapter and mount
    adapter = FlaskAdapter(flask_app)
    flask_router = cls(prefix=prefix, description=f"Flask app: {flask_app.name}")
    
    # Phase 1: "just make it work" - mount Flask app
    adapter.mount_to_router(flask_router)
    
    return flask_router

# Monkey patch the Router class to add from_flask method
Router.from_flask = classmethod(from_flask)
