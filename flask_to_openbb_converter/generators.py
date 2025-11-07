"""
Code Generation Module

This module contains generators for creating OpenBB-compatible code from Flask route analysis.
Includes providers, routers, and Pydantic models.
"""

from typing import Dict, List, Any, Optional
from textwrap import dedent, indent


class ProviderGenerator:
    """Generates OpenBB Provider code from Flask route information."""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
    
    def generate_from_routes(self, routes_info: List[Dict[str, Any]]) -> str:
        """Generate complete provider module from route information."""
        
        # Generate imports
        imports = self._generate_imports(routes_info)
        
        # Generate fetcher classes
        fetchers = []
        fetcher_dict_entries = []
        
        for route in routes_info:
            fetcher_class = self._generate_fetcher_class(route)
            fetchers.append(fetcher_class)
            
            model_name = route['pydantic_model_name']
            fetcher_name = f"{model_name}Fetcher"
            fetcher_dict_entries.append(f'        "{model_name}": {fetcher_name},')
        
        # Generate provider instance
        provider_instance = self._generate_provider_instance(fetcher_dict_entries)
        
        # Combine all parts
        code_parts = [
            imports,
            '\n'.join(fetchers),
            provider_instance
        ]
        
        return '\n\n'.join(code_parts)
    
    def _generate_imports(self, routes_info: List[Dict[str, Any]]) -> str:
        """Generate import statements for the provider."""
        return dedent('''
        """Flask-converted OpenBB Provider."""
        
        import requests
        from typing import Any, Dict, List, Optional
        from openbb_core.provider.abstract.fetcher import Fetcher
        from openbb_core.provider.abstract.provider import Provider
        from openbb_core.provider.standard_models.base import Data
        from pydantic import BaseModel, Field
        ''').strip()
    
    def _generate_fetcher_class(self, route_info: Dict[str, Any]) -> str:
        """Generate a fetcher class for a single route."""
        
        model_name = route_info['pydantic_model_name']
        fetcher_name = f"{model_name}Fetcher"
        function_name = route_info['function_name']
        
        # Generate query parameters class
        query_params_class = self._generate_query_params_class(route_info)
        
        # Generate data model class  
        data_model_class = self._generate_data_model_class(route_info)
        
        # Generate fetcher class
        fetcher_class = f'''
class {fetcher_name}(Fetcher[{model_name}QueryParams, List[{model_name}Data]]):
    """Fetcher for {function_name} endpoint converted from Flask."""
    
    @staticmethod
    def transform_query(params: Dict[str, Any]) -> {model_name}QueryParams:
        """Transform query parameters."""
        return {model_name}QueryParams(**params)
    
    @staticmethod
    async def aextract_data(
        query: {model_name}QueryParams,
        credentials: Optional[Dict[str, Any]],
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """Extract data from Flask endpoint."""
        
        # Get Flask base URL from credentials
        base_url = credentials.get("flask_base_url", "http://localhost:5000") if credentials else "http://localhost:5000"
        
        # Build endpoint URL
        endpoint_url = f"{{base_url}}{route_info['rule']}"
        
        # Handle URL parameters
        {self._generate_url_parameter_handling(route_info)}
        
        # Handle query parameters  
        params = {{}}
        {self._generate_query_parameter_handling(route_info)}
        
        # Make request to Flask endpoint
        response = requests.get(endpoint_url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        # Ensure data is a list
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            data = [data]
            
        return data
    
    @staticmethod
    def transform_data(
        query: {model_name}QueryParams,
        data: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> List[{model_name}Data]:
        """Transform data to Pydantic models."""
        return [{model_name}Data.model_validate(item) for item in data]
'''
        
        return query_params_class + '\n' + data_model_class + '\n' + fetcher_class
    
    def _generate_query_params_class(self, route_info: Dict[str, Any]) -> str:
        """Generate query parameters class."""
        
        model_name = route_info['pydantic_model_name']
        class_name = f"{model_name}QueryParams"
        
        # Combine URL and query parameters
        all_params = []
        
        # Add URL parameters
        for param in route_info['url_parameters']:
            all_params.append({
                'name': param,
                'type': 'str',
                'required': True,
                'description': f'URL parameter: {param}'
            })
        
        # Add query parameters
        for param in route_info['query_parameters']:
            all_params.append({
                'name': param['name'],
                'type': param['type'],
                'required': param['required'],
                'default': param['default'],
                'description': f'Query parameter: {param["name"]}'
            })
        
        if not all_params:
            # No parameters - create minimal class
            return f'''
class {class_name}(BaseModel):
    """Query parameters for {route_info['function_name']}."""
    pass
'''
        
        # Generate parameter fields
        fields = []
        for param in all_params:
            field_def = f"    {param['name']}: "
            
            if param['required']:
                field_def += f"{param['type']}"
            else:
                field_def += f"Optional[{param['type']}]"
                if param.get('default'):
                    field_def += f" = {repr(param['default'])}"
                else:
                    field_def += " = None"
            
            field_def += f' = Field(description="{param["description"]}")'
            fields.append(field_def)
        
        return f'''
class {class_name}(BaseModel):
    """Query parameters for {route_info['function_name']}."""
    
{chr(10).join(fields)}
'''
    
    def _generate_data_model_class(self, route_info: Dict[str, Any]) -> str:
        """Generate data model class."""
        
        model_name = route_info['pydantic_model_name']
        class_name = f"{model_name}Data"
        
        # For now, create a flexible model - in production, this would analyze response structure
        return f'''
class {class_name}(Data):
    """Data model for {route_info['function_name']} response."""
    
    # Flexible model - add specific fields based on actual Flask response structure
    data: Dict[str, Any] = Field(description="Response data from Flask endpoint")
'''
    
    def _generate_url_parameter_handling(self, route_info: Dict[str, Any]) -> str:
        """Generate code to handle URL parameters."""
        if not route_info['url_parameters']:
            return "# No URL parameters"
        
        handling_code = []
        for param in route_info['url_parameters']:
            handling_code.append(f'        endpoint_url = endpoint_url.replace("<{param}>", str(query.{param}))')
        
        return '\n'.join(handling_code)
    
    def _generate_query_parameter_handling(self, route_info: Dict[str, Any]) -> str:
        """Generate code to handle query parameters."""
        if not route_info['query_parameters']:
            return "        # No query parameters"
        
        handling_code = []
        for param in route_info['query_parameters']:
            param_name = param['name']
            if param['required']:
                handling_code.append(f'        params["{param_name}"] = query.{param_name}')
            else:
                handling_code.append(f'        if query.{param_name} is not None:')
                handling_code.append(f'            params["{param_name}"] = query.{param_name}')
        
        return '\n'.join(handling_code)
    
    def _generate_provider_instance(self, fetcher_dict_entries: List[str]) -> str:
        """Generate the provider instance."""
        
        fetcher_dict = '{\n' + '\n'.join(fetcher_dict_entries) + '\n    }'
        
        return f'''
{self.provider_name} = Provider(
    name="{self.provider_name}",
    website="https://github.com/converted-from-flask",
    description="Provider converted from Flask application using Flask-to-OpenBB Converter",
    credentials=["flask_base_url"],  # Flask application base URL
    fetcher_dict={fetcher_dict},
)
'''


class RouterGenerator:
    """Generates OpenBB Router code from Flask route information."""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.router_name = provider_name.replace('_provider', '')
    
    def generate_from_routes(self, routes_info: List[Dict[str, Any]]) -> str:
        """Generate complete router module from route information."""
        
        # Generate imports
        imports = self._generate_imports()
        
        # Generate router commands
        commands = []
        for route in routes_info:
            command = self._generate_router_command(route)
            commands.append(command)
        
        # Combine all parts
        code_parts = [
            imports,
            '\n'.join(commands)
        ]
        
        return '\n\n'.join(code_parts)
    
    def _generate_imports(self) -> str:
        """Generate import statements for the router."""
        return dedent(f'''
        """Flask-converted OpenBB Router."""
        
        from typing import Any, Dict, List, Optional
        from openbb_core.app.model.command_context import CommandContext
        from openbb_core.app.model.example import APIEx
        from openbb_core.app.model.obbject import OBBject
        from openbb_core.app.provider_interface import (
            ExtraParams,
            ProviderChoices,
            StandardParams,
        )
        from openbb_core.app.query import Query
        from openbb_core.app.router import Router
        
        router = Router(prefix="/{self.router_name}")
        ''').strip()
    
    def _generate_router_command(self, route_info: Dict[str, Any]) -> str:
        """Generate a router command for a single route."""
        
        command_name = route_info['openbb_command_name']
        model_name = route_info['pydantic_model_name']
        function_name = route_info['function_name']
        docstring = route_info['docstring'] or f"Converted from Flask endpoint: {route_info['rule']}"
        
        # Generate function parameters
        params = self._generate_function_parameters(route_info)
        
        # Generate function body
        function_body = self._generate_function_body(route_info, model_name)
        
        return f'''
@router.command(
    model="{model_name}",
    examples=[
        APIEx(
            description="Get data from converted Flask endpoint",
            parameters={self._generate_example_parameters(route_info)},
        )
    ],
)
async def {command_name}(
    cc: CommandContext,
    provider_choices: ProviderChoices,
    standard_params: StandardParams,
    extra_params: ExtraParams,
{params}
) -> OBBject:
    """
    {docstring}
    
    Converted from Flask endpoint: {route_info['rule']}
    Original function: {function_name}
    """
{function_body}
'''
    
    def _generate_function_parameters(self, route_info: Dict[str, Any]) -> str:
        """Generate function parameters for router command."""
        params = []
        
        # Add URL parameters
        for param in route_info['url_parameters']:
            params.append(f'    {param}: str,')
        
        # Add query parameters
        for param in route_info['query_parameters']:
            param_type = param['type']
            if not param['required']:
                param_type = f"Optional[{param_type}]"
                default = f" = {repr(param['default'])}" if param.get('default') else " = None"
            else:
                default = ""
            
            params.append(f'    {param["name"]}: {param_type}{default},')
        
        return '\n'.join(params)
    
    def _generate_function_body(self, route_info: Dict[str, Any], model_name: str) -> str:
        """Generate function body for router command."""
        
        # Build query parameters
        query_params = []
        
        # Add URL parameters
        for param in route_info['url_parameters']:
            query_params.append(f'        "{param}": {param},')
        
        # Add query parameters
        for param in route_info['query_parameters']:
            param_name = param['name']
            if param['required']:
                query_params.append(f'        "{param_name}": {param_name},')
            else:
                query_params.append(f'        "{param_name}": {param_name},')
        
        query_dict = '{\n' + '\n'.join(query_params) + '\n    }' if query_params else '{}'
        
        return f'''    return await OBBject.from_query(
        Query(
            **{query_dict}
        )
    )'''
    
    def _generate_example_parameters(self, route_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate example parameters for API documentation."""
        examples = {}
        
        # Add URL parameters
        for param in route_info['url_parameters']:
            examples[param] = "example_value"
        
        # Add query parameters
        for param in route_info['query_parameters']:
            if param['type'] == 'str':
                examples[param['name']] = "example_string"
            elif param['type'] == 'int':
                examples[param['name']] = 100
            elif param['type'] == 'bool':
                examples[param['name']] = True
            else:
                examples[param['name']] = "example_value"
        
        return examples


class ModelGenerator:
    """Generates Pydantic model code from Flask route responses."""
    
    def generate_from_routes(self, routes_info: List[Dict[str, Any]]) -> Dict[str, str]:
        """Generate Pydantic models from route information."""
        models = {}
        
        for route in routes_info:
            model_name = route['pydantic_model_name']
            model_code = self._generate_model_code(route)
            models[model_name.lower()] = model_code
        
        return models
    
    def _generate_model_code(self, route_info: Dict[str, Any]) -> str:
        """Generate Pydantic model code for a single route."""
        
        model_name = route_info['pydantic_model_name']
        function_name = route_info['function_name']
        
        return f'''
"""Pydantic models for {function_name} endpoint."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from openbb_core.provider.standard_models.base import Data


class {model_name}(Data):
    """Data model for {function_name} response."""
    
    # TODO: Define specific fields based on actual Flask response structure
    # This is a flexible model that accepts any data structure
    data: Dict[str, Any] = Field(description="Response data from Flask endpoint")
    
    @classmethod
    def model_validate(cls, data: Any) -> "{model_name}":
        """Validate and create model instance."""
        if isinstance(data, dict):
            return cls(data=data)
        else:
            return cls(data={{"value": data}})
'''