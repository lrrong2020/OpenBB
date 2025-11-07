# Flask Adapter Extension for OpenBB Platform

Enables mounting Flask applications as OpenBB extensions.

## Phase 1: Entry Point Implementation

This extension implements Darren Lee's Phase 1 specification for Flask adapter integration.

### Features

- `Router.from_flask()` class method for mounting Flask apps
- Automatic Flask route discovery and analysis
- Zero Flask dependency in openbb-core
- Foundation for Phase 2 Widget Factory

### Usage

```python
from flask import Flask
from openbb_core.app.router import Router

# Create Flask app
app = Flask(__name__)

@app.route('/test')
def test_endpoint():
    return {"message": "Hello from Flask"}

# Mount to OpenBB
flask_router = Router.from_flask(app, prefix="/my_flask_app")
```

### Implementation Status

- ✅ Phase 1: Entry Point (Router.from_flask)
- ⏳ Phase 2: Widget Factory (Future)
- ⏳ Phase 3: Python Static Files (Future)

### Author

Boris Li <boris.quan.li@gmail.com>
