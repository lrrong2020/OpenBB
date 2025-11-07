"""
Flask to OpenBB Conversion Toolkit

This module provides tools to convert existing Flask applications into OpenBB-compatible
providers, routers, and data models, enabling seamless integration with the OpenBB ecosystem.

Key Features:
- Automatic Flask route introspection
- OpenBB Provider generation from Flask endpoints
- Pydantic model creation from Flask responses
- Type annotation inference and validation
- Enterprise migration documentation

Usage:
    from flask_to_openbb_converter import FlaskToOpenBBConverter
    
    # Convert existing Flask app
    converter = FlaskToOpenBBConverter(flask_app_instance)
    provider = converter.generate_provider()
    router = converter.generate_router()
"""

from .converter import FlaskToOpenBBConverter
from .introspection import FlaskRouteIntrospector
from .generators import ProviderGenerator, RouterGenerator, ModelGenerator

__version__ = "0.1.0"
__author__ = "Boris Li <boris.quan.li@gmail.com>"

__all__ = [
    "FlaskToOpenBBConverter",
    "FlaskRouteIntrospector", 
    "ProviderGenerator",
    "RouterGenerator",
    "ModelGenerator",
]