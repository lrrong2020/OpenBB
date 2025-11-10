#!/usr/bin/env python3
"""
Direct Flask Entry Point Demo

This demonstrates Darren's suggested approach where Flask apps are loaded
directly via pyproject.toml entry points instead of wrapper extensions.

Example pyproject.toml entry:
[project.entry-points."openbb_core_extension"]
flask_financial_api = "demo_direct_flask_entry_point:app"
"""

from flask import Flask, request, jsonify

# Create Flask app instance that can be referenced directly
app = Flask(__name__)

@app.route('/')
def root():
    """Root endpoint for financial data API."""
    return jsonify({"message": "Financial Data API", "version": "1.0"})

@app.route('/sectors/')
def sectors():
    """Get sector performance data."""
    financial_indicator = request.args.get('financial_indicator', 'revenue')
    return jsonify({
        'sectors': ['Technology', 'Healthcare', 'Finance'],
        'indicator': financial_indicator,
        'data': {
            'Technology': 150.2,
            'Healthcare': 89.7,
            'Finance': 67.3
        }
    })

@app.route('/sectors/<sector_name>')
def sector_details(sector_name):
    """Get detailed sector information."""
    return jsonify({
        'sector': sector_name,
        'companies': ['AAPL', 'MSFT', 'GOOGL'] if sector_name == 'Technology' else ['COMP1', 'COMP2'],
        'performance': {
            'quarterly_return': 0.15,
            'volatility': 0.23
        }
    })

if __name__ == '__main__':
    # For development/testing
    app.run(debug=True, port=5000)