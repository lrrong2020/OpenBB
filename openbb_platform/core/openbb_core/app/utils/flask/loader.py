"""Flask extension loading integration."""

from typing import Any, Optional
from .introspection import _check_flask_available
from .adapter import FlaskToOpenBBAdapter

class FlaskExtensionLoader:
    """Integrates Flask app loading with OpenBB's extension system."""
    
    @staticmethod
    def detect_flask_entry_point(entry_point: str) -> bool:
        """Detect if an entry point references a Flask application."""
        try:
            module_path, app_name = entry_point.split(':')
            module = __import__(module_path, fromlist=[app_name])
            app = getattr(module, app_name)
            return FlaskExtensionLoader.validate_flask_app(app)
        except Exception:
            return False
    
    @staticmethod
    def load_flask_extension(entry_point: str, prefix: str) -> Optional[Any]:
        """Load Flask app as OpenBB extension."""
        try:
            if not _check_flask_available():
                return None
                
            module_path, app_name = entry_point.split(':')
            module = __import__(module_path, fromlist=[app_name])
            flask_app = getattr(module, app_name)
            
            if FlaskExtensionLoader.validate_flask_app(flask_app):
                adapter = FlaskToOpenBBAdapter(flask_app, f"{prefix}_provider")
                return {
                    'provider_code': adapter.generate_provider_code(),
                    'router_code': adapter.generate_router_code(),
                    'models': adapter.generate_pydantic_models()
                }
            return None
        except Exception as e:
            print(f"Error loading Flask extension {entry_point}: {e}")
            return None
    
    @staticmethod
    def validate_flask_app(app: Any) -> bool:
        """Validate that the loaded object is a proper Flask application."""
        try:
            return (
                hasattr(app, 'url_map') and
                hasattr(app, 'view_functions') and
                hasattr(app, 'name')
            )
        except Exception:
            return False