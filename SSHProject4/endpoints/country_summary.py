"""
Country Summary Endpoint
Returns comprehensive data for all countries with discovery metrics
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_country_summary(app):
    """Register country summary endpoint for discovery tables"""
    
    @app.route('/api/country_summary', methods=['GET'])
    def get_country_summary():
        """Get comprehensive summary data for all countries"""
        start, end = parse_date_params()
        
        conn = get_db()
        
        query = f"""
            WITH country_stats AS (
                SELECT 
                    country,
                    SUM(attacks) as total_attacks,
                    AVG(attacks) as avg_daily,
                    COUNT(DISTINCT date) as active_days,
                    MIN(date) as first_seen,
                    MAX(date) as last_seen,
                    MAX(attacks) as max_daily
                FROM daily_country_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND country != 'Unknown'
                GROUP BY country
            ),
            with_volatility AS (
                SELECT 
                    cs.*,
                    COALESCE(v.max_volatility, 0) as volatility,
                    DATE_DIFF('day', cs.first_seen, cs.last_seen) + 1 as date_span
                FROM country_stats cs
                LEFT JOIN volatile_country_summary v ON cs.country = v.country
            )
            SELECT 
                country,
                total_attacks,
                ROUND(avg_daily, 2) as avg_daily,
                active_days,
                first_seen::VARCHAR as first_seen,
                last_seen::VARCHAR as last_seen,
                ROUND(volatility, 2) as volatility,
                max_daily,
                date_span,
                CASE 
                    WHEN date_span > 0 THEN ROUND((active_days::FLOAT / date_span) * 100, 1)
                    ELSE 0 
                END as persistence_pct
            FROM with_volatility
            ORDER BY total_attacks DESC
        """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{
            'country': row[0],
            'total_attacks': row[1],
            'avg_daily': row[2],
            'active_days': row[3],
            'first_seen': row[4],
            'last_seen': row[5],
            'volatility': row[6],
            'max_daily': row[7],
            'date_span': row[8],
            'persistence_pct': row[9]
        } for row in result]
        
        return jsonify(data)