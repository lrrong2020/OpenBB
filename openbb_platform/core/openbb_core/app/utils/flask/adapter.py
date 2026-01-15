"""Flask-to-OpenBB conversion logic."""

from typing import Any
from openbb_core.app.router import Router
from openbb_core.app.model.obbject import OBBject
from .introspection import FlaskIntrospector

def is_flask_available() -> bool:
    """Check if Flask is available."""
    try:
        import flask
        return True
    except ImportError:
        return False

def create_flask_router(flask_app: Any, prefix: str = "/flask") -> Router:
    """Create OpenBB router from Flask app with metadata layer."""
    if not is_flask_available():
        raise ImportError("Flask is not available")
    
    router = Router(prefix=prefix)
    introspector = FlaskIntrospector(flask_app)
    routes = introspector.analyze_routes()
    
    for route_info in routes:
        _add_flask_route_to_router(router, route_info, flask_app)
    
    return router

def _add_flask_route_to_router(router: Router, route_info: dict, flask_app: Any) -> None:
    """Add a Flask route to OpenBB router with metadata."""
    docstring_info = route_info.get('docstring_info', {})
    
    def flask_wrapper(**kwargs) -> OBBject:
        with flask_app.test_client() as client:
            response = client.get(route_info['rule'], query_string=kwargs)
            return OBBject(results=response.get_json())
    
    flask_wrapper.__name__ = route_info['openbb_command_name']
    flask_wrapper.__doc__ = route_info.get('docstring', '')
    
    router.command(
        flask_wrapper,
        methods=['GET'],
        summary=docstring_info.get('summary'),
        description=docstring_info.get('description'),
    )