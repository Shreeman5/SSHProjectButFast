"""
Date Range Endpoint
Returns the available date range in the database
"""

from flask import jsonify
from utils.db import get_db


def register_date_range(app):
    """Register date range endpoint"""
    
    @app.route('/api/date_range', methods=['GET'])
    def get_date_range():
        """Get available date range"""
        conn = get_db()
        result = conn.execute("""
            SELECT 
                MIN(date)::VARCHAR as min_date,
                MAX(date)::VARCHAR as max_date
            FROM daily_stats
        """).fetchone()
        conn.close()
        
        return jsonify({
            'min_date': result[0] if result else None,
            'max_date': result[1] if result else None
        })
