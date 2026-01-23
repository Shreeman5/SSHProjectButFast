#!/usr/bin/env python3
"""
Flask API for Attack Data Visualizations
Main application file - imports and registers all endpoints
"""

from flask import Flask
from flask_cors import CORS

# Create Flask app
app = Flask(__name__)
CORS(app)

# Import and register endpoint blueprints
from endpoints.total_attacks import register_total_attacks
from endpoints.country_attacks import register_country_attacks
from endpoints.unusual_countries import register_unusual_countries
from endpoints.ip_attacks import register_ip_attacks
from endpoints.username_attacks import register_username_attacks
from endpoints.asn_attacks import register_asn_attacks
from endpoints.date_range import register_date_range
from endpoints.index import register_index

# Register all endpoints
register_total_attacks(app)
register_country_attacks(app)
register_unusual_countries(app)
register_ip_attacks(app)
register_username_attacks(app)
register_asn_attacks(app)
register_date_range(app)
register_index(app)

if __name__ == '__main__':
    from utils.config import DB_PATH
    
    print("="*70)
    print("Attack Data Visualization API")
    print("Using ONLY summary tables (no raw data queries)")
    print("="*70)
    print(f"\n📊 Database: {DB_PATH}")
    print(f"🌐 Server: http://localhost:5000")
    print(f"📝 API Docs: http://localhost:5000")
    print("\n✅ This version avoids file limit issues!")
    print("="*70)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
