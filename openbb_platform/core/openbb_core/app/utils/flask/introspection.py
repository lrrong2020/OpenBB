"""Flask route analysis and introspection utilities."""

import inspect
import re
import sys
from typing import Any, Dict, List, Optional
from werkzeug.routing import Rule

def _check_flask_available() -> bool:
    """Check if Flask is available without importing it."""
    return 'flask' in sys.modules or _can_import_flask()

def _can_import_flask() -> bool:
    """Safely attempt Flask import."""
    try:
        import flask
        return True
    except ImportError:
        return False

class FlaskIntrospector:
    """Analyzes Flask applications to extract route information."""
    
    def __init__(self, flask_app: Any):
        if not _check_flask_available():
            raise ImportError("Flask is not available in the current environment")
        self.flask_app = flask_app
        self.url_map = flask_app.url_map
    
    def analyze_routes(self) -> List[Dict[str, Any]]:
        """Analyze all routes in the Flask application."""
        routes_info = []
        
        for rule in self.url_map.iter_rules():
            if rule.endpoint != 'static':  # Skip static file routes
                route_info = self._analyze_single_route(rule)
                if route_info:
                    routes_info.append(route_info)
        
        return routes_info
    
    def _analyze_single_route(self, rule: Rule) -> Optional[Dict[str, Any]]:
        """Analyze a single Flask route."""
        try:
            view_function = self.flask_app.view_functions.get(rule.endpoint)
            if not view_function:
                return None
            
            route_info = {
                'rule': rule.rule,
                'endpoint': rule.endpoint,
                'methods': list(rule.methods - {'HEAD', 'OPTIONS'}),
                'function_name': view_function.__name__,
                'function': view_function,
                'url_parameters': list(rule.arguments),
                'query_parameters': self._extract_query_parameters(view_function),
                'docstring': self._extract_docstring(view_function),
                'return_type': self._infer_return_type(view_function),
                'openbb_command_name': self._generate_openbb_command_name(rule.rule, view_function.__name__),
                'pydantic_model_name': self._generate_model_name(view_function.__name__),
            }
            
            return route_info
            
        except Exception as e:
            print(f"Warning: Could not analyze route {rule.rule}: {e}")
            return None
    
    def _extract_query_parameters(self, view_function) -> List[Dict[str, Any]]:
        """Extract query parameters from Flask view function."""
        query_params = []
        
        try:
            source = inspect.getsource(view_function)
            param_pattern = r'request\.args\.get\([\'"]([^\'\"]+)[\'"](?:,\s*[\'"]?([^\'\"]*)[\'"]?)?\)'
            matches = re.findall(param_pattern, source)
            
            for match in matches:
                param_name = match[0]
                default_value = match[1] if len(match) > 1 and match[1] else None
                
                query_params.append({
                    'name': param_name,
                    'default': default_value,
                    'type': self._infer_parameter_type(default_value),
                    'required': default_value is None
                })
                
        except Exception as e:
            print(f"Warning: Could not extract query parameters from {view_function.__name__}: {e}")
        
        return query_params
    
    def _extract_docstring(self, view_function) -> Optional[str]:
        """Extract and clean docstring from view function."""
        docstring = inspect.getdoc(view_function)
        if docstring:
            lines = docstring.strip().split('\n')
            cleaned_lines = [line.strip() for line in lines if line.strip()]
            return ' '.join(cleaned_lines)
        return None
    
    def _infer_return_type(self, view_function) -> str:
        """Infer the return type of a Flask view function."""
        try:
            signature = inspect.signature(view_function)
            if signature.return_annotation != inspect.Signature.empty:
                return str(signature.return_annotation)
            
            source = inspect.getsource(view_function)
            
            if 'json.dumps' in source or 'jsonify' in source:
                return 'Dict[str, Any]'
            elif 'return {' in source:
                return 'Dict[str, Any]'
            elif 'return [' in source:
                return 'List[Dict[str, Any]]'
            else:
                return 'Any'
                
        except Exception:
            return 'Any'
    
    def _infer_parameter_type(self, default_value: Optional[str]) -> str:
        """Infer parameter type from default value."""
        if default_value is None:
            return 'str'
        elif default_value.isdigit():
            return 'int'
        elif default_value.lower() in ['true', 'false']:
            return 'bool'
        else:
            return 'str'
    
    def _generate_openbb_command_name(self, rule: str, function_name: str) -> str:
        """Generate OpenBB command name from Flask route."""
        clean_rule = rule.lstrip('/')
        clean_rule = re.sub(r'<[^>]+>', '', clean_rule)
        clean_rule = clean_rule.strip('/')
        
        command_name = clean_rule.replace('/', '_').replace('-', '_')
        
        if not command_name or command_name == '_':
            command_name = function_name
        
        command_name = re.sub(r'_+', '_', command_name)
        command_name = command_name.strip('_')
        
        return command_name or function_name
    
    def _generate_model_name(self, function_name: str) -> str:
        """Generate Pydantic model name from function name."""
        words = function_name.split('_')
        model_name = ''.join(word.capitalize() for word in words)
        
        if not model_name.endswith(('Data', 'Response', 'Model')):
            model_name += 'Data'
        
        return model_name