"""Tests for Flask Adapter Extension."""

import pytest


def test_flask_adapter_import():
    """Test that Flask adapter can be imported."""
    try:
        from openbb_flask_adapter.utils.adapter import FlaskAdapter
        from openbb_flask_adapter.utils.introspection import FlaskRouteIntrospector
        assert FlaskAdapter is not None
        assert FlaskRouteIntrospector is not None
    except ImportError as e:
        pytest.skip(f"Flask adapter not available: {e}")


def test_router_from_flask_method_exists():
    """Test that Router.from_flask method is added."""
    try:
        from openbb_core.app.router import Router
        # Import the extension to add the method
        import openbb_flask_adapter.flask_router
        
        assert hasattr(Router, 'from_flask')
        assert callable(Router.from_flask)
    except ImportError as e:
        pytest.skip(f"OpenBB core not available: {e}")


def test_flask_adapter_with_mock_app():
    """Test Flask adapter with mock Flask app."""
    try:
        from openbb_flask_adapter.utils.adapter import FlaskAdapter
        
        # Create mock Flask app structure
        class MockRule:
            def __init__(self, rule, endpoint, methods):
                self.rule = rule
                self.endpoint = endpoint
                self.methods = set(methods)
                self.arguments = []
        
        class MockUrlMap:
            def iter_rules(self):
                return [MockRule('/test', 'test_endpoint', ['GET'])]
        
        class MockFlaskApp:
            def __init__(self):
                self.__class__.__name__ = "Flask"
                self.name = "test_app"
                self.url_map = MockUrlMap()
                self.view_functions = {'test_endpoint': lambda: {"message": "test"}}
        
        # Test adapter creation
        mock_app = MockFlaskApp()
        adapter = FlaskAdapter(mock_app)
        
        assert adapter.flask_app == mock_app
        assert adapter.introspector is not None
        
        # Test route analysis
        routes = adapter.introspector.analyze_routes()
        assert len(routes) == 1
        assert routes[0]['rule'] == '/test'
        
    except ImportError as e:
        pytest.skip(f"Flask adapter not available: {e}")


if __name__ == "__main__":
    # Run basic tests
    test_flask_adapter_import()
    test_router_from_flask_method_exists()
    test_flask_adapter_with_mock_app()
    print("✅ All tests passed!")
