#!/usr/bin/env python3
"""
Test Flask to OpenBB Converter

This script tests the Flask-to-OpenBB converter functionality to ensure
it correctly analyzes Flask routes and generates valid OpenBB code.
"""

import pytest
from flask import Flask, request, jsonify
from flask_to_openbb_converter import FlaskToOpenBBConverter


def create_test_flask_app():
    """Create a simple Flask app for testing."""
    app = Flask(__name__)
    
    @app.route('/')
    def root():
        """Root endpoint."""
        return "Test Flask App"
    
    @app.route('/sectors/')
    def sectors():
        """
        Get sector performance data.
        Returns quarterly average financial indicators for all sectors.
        """
        financial_indicator = request.args.get('financial_indicator', 'revenue')
        return jsonify({
            'sectors': ['Technology', 'Healthcare', 'Finance'],
            'indicator': financial_indicator,
            'data': [100, 200, 300]
        })
    
    @app.route('/sectors/<sector_name>')
    def sector_details(sector_name):
        """Get detailed information for a specific sector."""
        return jsonify({
            'sector': sector_name,
            'companies': ['AAPL', 'MSFT', 'GOOGL'],
            'performance': 0.15
        })
    
    @app.route('/companies/search')
    def search_companies():
        """Search companies with multiple parameters."""
        sector = request.args.get('sector')
        min_market_cap = request.args.get('min_market_cap', '1000000000')
        include_etfs = request.args.get('include_etfs', 'false')
        
        return jsonify({
            'sector': sector,
            'min_market_cap': int(min_market_cap),
            'include_etfs': include_etfs.lower() == 'true',
            'results': []
        })
    
    return app


def test_flask_route_introspection():
    """Test Flask route analysis."""
    print("🧪 Testing Flask route introspection...")
    
    app = create_test_flask_app()
    converter = FlaskToOpenBBConverter(app, provider_name="test_provider")
    
    # Test route analysis
    routes_info = converter.introspector.analyze_routes()
    
    # Should find 4 routes (excluding static)
    assert len(routes_info) == 4, f"Expected 4 routes, found {len(routes_info)}"
    
    # Check specific routes
    route_rules = [route['rule'] for route in routes_info]
    expected_routes = ['/', '/sectors/', '/sectors/<sector_name>', '/companies/search']
    
    for expected_route in expected_routes:
        assert expected_route in route_rules, f"Route {expected_route} not found"
    
    print("✅ Route introspection test passed")


def test_provider_generation():
    """Test OpenBB provider code generation."""
    print("🧪 Testing provider code generation...")
    
    app = create_test_flask_app()
    converter = FlaskToOpenBBConverter(app, provider_name="test_provider")
    
    # Generate provider code
    provider_code = converter.generate_provider_code()
    
    # Basic validation
    assert "class" in provider_code, "Provider code should contain class definitions"
    assert "Fetcher" in provider_code, "Provider code should contain Fetcher classes"
    assert "test_provider" in provider_code, "Provider code should reference provider name"
    assert "async def aextract_data" in provider_code, "Provider should have async extract method"
    
    print("✅ Provider generation test passed")


def test_router_generation():
    """Test OpenBB router code generation."""
    print("🧪 Testing router code generation...")
    
    app = create_test_flask_app()
    converter = FlaskToOpenBBConverter(app, provider_name="test_provider")
    
    # Generate router code
    router_code = converter.generate_router_code()
    
    # Basic validation
    assert "@router.command" in router_code, "Router code should contain command decorators"
    assert "async def" in router_code, "Router code should contain async functions"
    assert "OBBject" in router_code, "Router code should return OBBject"
    
    print("✅ Router generation test passed")


def test_model_generation():
    """Test Pydantic model generation."""
    print("🧪 Testing model generation...")
    
    app = create_test_flask_app()
    converter = FlaskToOpenBBConverter(app, provider_name="test_provider")
    
    # Generate models
    models_code = converter.generate_models_code()
    
    # Should generate models for each route
    assert len(models_code) > 0, "Should generate at least one model"
    
    # Check model content
    for model_name, model_code in models_code.items():
        assert "class" in model_code, f"Model {model_name} should contain class definition"
        assert "BaseModel" in model_code or "Data" in model_code, f"Model {model_name} should inherit from BaseModel or Data"
    
    print("✅ Model generation test passed")


def test_complete_extension_generation():
    """Test complete extension generation."""
    print("🧪 Testing complete extension generation...")
    
    app = create_test_flask_app()
    converter = FlaskToOpenBBConverter(app, provider_name="test_provider")
    
    # Generate complete extension
    extension_files = converter.generate_complete_extension()
    
    # Check required files
    required_files = ['provider/__init__.py', 'router/__init__.py', 'pyproject.toml', 'README.md']
    
    for required_file in required_files:
        assert required_file in extension_files, f"Missing required file: {required_file}"
        assert len(extension_files[required_file]) > 0, f"File {required_file} should not be empty"
    
    print("✅ Complete extension generation test passed")


def test_route_summary():
    """Test route summary functionality."""
    print("🧪 Testing route summary...")
    
    app = create_test_flask_app()
    converter = FlaskToOpenBBConverter(app, provider_name="test_provider")
    
    # Get route summary
    summary = converter.introspector.get_route_summary()
    
    # Validate summary
    assert summary['total_routes'] == 4, f"Expected 4 routes in summary, got {summary['total_routes']}"
    assert 'GET' in summary['methods_used'], "Should detect GET methods"
    assert summary['has_parameters'], "Should detect routes with parameters"
    
    print("✅ Route summary test passed")


def run_all_tests():
    """Run all converter tests."""
    print("🚀 Running Flask-to-OpenBB Converter Tests")
    print("=" * 50)
    
    try:
        test_flask_route_introspection()
        test_provider_generation()
        test_router_generation()
        test_model_generation()
        test_complete_extension_generation()
        test_route_summary()
        
        print("\n🎉 All tests passed successfully!")
        print("\n✅ Flask-to-OpenBB Converter is working correctly")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)