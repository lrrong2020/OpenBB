"""Flask Route Introspection.

Minimal Flask route analyzer for Phase 1 implementation.
"""

import inspect
import re
from typing import Dict, List, Any, Optional


class FlaskRouteIntrospector:
    """Minimal Flask route analyzer.
    
    Extracts route information from Flask applications without
    requiring Flask as a dependency in openbb-core.
    """
    
    def __init__(self, flask_app):
        """Initialize introspector.
        
        Args:
            flask_app: Flask application instance
        """
        self.flask_app = flask_app
        
    def analyze_routes(self) -> List[Dict[str, Any]]:
        """Analyze Flask routes - minimal Phase 1 implementation.
        
        Returns:
            List of route information dictionaries
        """
        routes = []
        
        for rule in self.flask_app.url_map.iter_rules():
            if rule.endpoint != 'static':  # Skip Flask static routes
                view_func = self.flask_app.view_functions.get(rule.endpoint)
                if view_func:
                    route_info = {
                        'rule': rule.rule,
                        'endpoint': rule.endpoint,
                        'methods': list(rule.methods - {'HEAD', 'OPTIONS'}),
                        'function': view_func,
                        'function_name': view_func.__name__,
                        'openbb_command_name': self._to_openbb_command(rule.rule),
                        'url_parameters': list(rule.arguments),
                        'docstring': self._extract_docstring(view_func),
                    }
                    routes.append(route_info)
        
        return routes
    
    def _to_openbb_command(self, flask_rule: str) -> str:
        """Convert Flask route to OpenBB command format.
        
        Args:
            flask_rule: Flask route pattern (e.g., '/users/<id>')
            
        Returns:
            OpenBB command name (e.g., 'users_id')
        """
        # Remove leading slash and parameter brackets
        clean_rule = flask_rule.lstrip('/')
        clean_rule = re.sub(r'<[^>]*>', 'param', clean_rule)  # Replace <param> with 'param'
        clean_rule = clean_rule.replace('/', '_').replace('-', '_')
        
        # Clean up multiple underscores and ensure valid identifier
        clean_rule = re.sub(r'_+', '_', clean_rule)
        clean_rule = clean_rule.strip('_')
        
        return clean_rule or 'root'
    
    def _extract_docstring(self, view_function) -> Optional[str]:
        """Extract docstring from Flask view function.
        
        Args:
            view_function: Flask view function
            
        Returns:
            Cleaned docstring or None
        """
        docstring = inspect.getdoc(view_function)
        if docstring:
            # Clean up the docstring
            lines = docstring.strip().split('\n')
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            return ' '.join(cleaned_lines)
        return None
    
    def get_route_summary(self) -> Dict[str, Any]:
        """Get summary of Flask routes for debugging.
        
        Returns:
            Dictionary with route statistics and overview
        """
        routes = self.analyze_routes()
        
        return {
            'total_routes': len(routes),
            'methods_used': list(set(method for route in routes for method in route['methods'])),
            'endpoints': [route['rule'] for route in routes],
            'functions': [route['function_name'] for route in routes],
            'has_parameters': len([r for r in routes if r['url_parameters']]) > 0,
            'documented_routes': len([r for r in routes if r['docstring']]) 
        }
