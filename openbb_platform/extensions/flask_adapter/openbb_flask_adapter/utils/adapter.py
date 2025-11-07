"""Flask Application Adapter.

Core logic for mounting Flask applications to OpenBB Router.
"""

from typing import TYPE_CHECKING, Any, Dict, List
from .introspection import FlaskRouteIntrospector

if TYPE_CHECKING:
    from openbb_core.app.router import Router


class FlaskAdapter:
    """Adapter to mount Flask apps to OpenBB Router.
    
    Phase 1 Implementation: Entry Point
    - Analyzes Flask routes using introspection
    - Mounts Flask functions to OpenBB router
    - Provides foundation for Phase 2 Widget Factory
    """
    
    def __init__(self, flask_app):
        """Initialize Flask adapter.
        
        Args:
            flask_app: Flask application instance
        """
        # Validate without importing Flask (avoid dependency)
        if flask_app.__class__.__name__ != "Flask":
            raise TypeError("Expected Flask application instance")
        
        self.flask_app = flask_app
        self.introspector = FlaskRouteIntrospector(flask_app)
        
    def mount_to_router(self, openbb_router: "Router") -> None:
        """Mount Flask app to OpenBB router.
        
        Phase 1: Simple mounting - "just make it work"
        
        Args:
            openbb_router: OpenBB Router instance to mount to
        """
        routes_info = self.introspector.analyze_routes()
        
        for route_info in routes_info:
            self._add_flask_route_to_openbb(openbb_router, route_info)
    
    def _add_flask_route_to_openbb(self, router: "Router", route_info: Dict[str, Any]) -> None:
        """Add individual Flask route to OpenBB router.
        
        Args:
            router: OpenBB Router instance
            route_info: Flask route metadata from introspection
        """
        flask_func = route_info['function']
        openbb_path = route_info['openbb_command_name']
        
        # Create OpenBB command wrapper for Flask function
        async def openbb_wrapper(**kwargs):
            """Wrapper to call original Flask function."""
            try:
                # Call original Flask function with parameters
                result = flask_func(**kwargs)
                
                # Ensure result is JSON serializable
                if hasattr(result, 'get_json'):
                    return result.get_json()
                return result
                
            except Exception as e:
                return {"error": str(e), "flask_route": route_info['rule']}
        
        # Set function metadata for OpenBB
        openbb_wrapper.__name__ = f"flask_{openbb_path}"
        openbb_wrapper.__doc__ = route_info.get('docstring', f"Flask route: {route_info['rule']}")
        
        # Add to OpenBB router (Phase 1 minimal implementation)
        try:
            router.api_router.add_api_route(
                path=f"/{openbb_path}",
                endpoint=openbb_wrapper,
                methods=route_info['methods'],
                summary=f"Flask: {route_info['rule']}",
                description=route_info.get('docstring', f"Mounted Flask route: {route_info['rule']}")
            )
        except Exception as e:
            # Skip problematic routes in Phase 1
            print(f"Warning: Could not mount Flask route {route_info['rule']}: {e}")
    
    def get_route_summary(self) -> Dict[str, Any]:
        """Get summary of Flask routes for debugging.
        
        Returns:
            Dictionary with route analysis summary
        """
        return self.introspector.get_route_summary()
