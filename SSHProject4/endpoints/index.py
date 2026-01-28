"""
Index Endpoint
API documentation and status
"""

from flask import jsonify


def register_index(app):
    """Register index endpoint"""
    
    @app.route('/')
    def index():
        """API documentation"""
        return jsonify({
            'name': 'Attack Data Visualization API',
            'status': 'running',
            'endpoints': {
                '/api/total_attacks': 'Total attacks over time',
                '/api/country_attacks': 'Top 10 countries',
                '/api/ip_attacks': 'Top 10 IPs',
                '/api/username_attacks': 'Top 10 usernames',
                '/api/asn_attacks': 'Top 10 ASNs',
                '/api/date_range': 'Available dates'
            },
            'note': 'Uses only summary tables - fast queries!'
        })