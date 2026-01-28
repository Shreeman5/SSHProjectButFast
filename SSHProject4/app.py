#!/usr/bin/env python3
"""
Flask API for Attack Data Visualizations
Main application file - imports and registers all endpoints
"""

from flask import Flask
from flask_cors import CORS

# Create Flask app
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Import and register endpoint blueprints
from endpoints.total_attacks import register_total_attacks
from endpoints.country_attacks import register_country_attacks
from endpoints.ip_attacks import register_ip_attacks
from endpoints.username_attacks import register_username_attacks
from endpoints.asn_attacks import register_asn_attacks
from endpoints.date_range import register_date_range
from endpoints.index import register_index

# NEW: Summary endpoints for discovery page
from endpoints.country_summary import register_country_summary
from endpoints.ip_summary import register_ip_summary
from endpoints.asn_summary import register_asn_summary
from endpoints.username_summary import register_username_summary

# Register all endpoints
register_total_attacks(app)
register_country_attacks(app)
register_ip_attacks(app)
register_username_attacks(app)
register_asn_attacks(app)
register_date_range(app)
register_index(app)

# Register summary endpoints
register_country_summary(app)
register_ip_summary(app)
register_asn_summary(app)
register_username_summary(app)

if __name__ == '__main__':
    from utils.config import DB_PATH
    
    print("="*70)
    print("Attack Data Visualization API")
    print("Using ONLY summary tables (no raw data queries)")
    print("="*70)
    print(f"\n📊 Database: {DB_PATH}")
    print(f"🌐 Server: http://localhost:5000")
    print(f"📝 API Docs: http://localhost:5000")
    print(f"🔍 Discovery Page: discovery.html")
    print("\n✅ This version avoids file limit issues!")
    print("="*70)
    
    app.run(debug=True, host='0.0.0.0', port=5000)