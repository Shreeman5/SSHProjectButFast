"""
ASN Summary Endpoint
Returns comprehensive data for all ASNs with discovery metrics
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_asn_summary(app):
    """Register ASN summary endpoint for discovery tables"""
    
    @app.route('/api/asn_summary', methods=['GET'])
    def get_asn_summary():
        """Get comprehensive summary data for all ASNs"""
        start, end = parse_date_params()
        
        conn = get_db()
        
        query = f"""
            WITH asn_stats AS (
                SELECT 
                    asn_name,
                    SUM(attacks) as total_attacks,
                    AVG(attacks) as avg_daily,
                    COUNT(DISTINCT date) as active_days,
                    COUNT(DISTINCT country) as countries,
                    MIN(date) as first_seen,
                    MAX(date) as last_seen,
                    MAX(attacks) as max_daily
                FROM daily_asn_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                GROUP BY asn_name
            ),
            with_volatility AS (
                SELECT 
                    asns.*,
                    COALESCE(v.max_volatility, 0) as volatility,
                    DATE_DIFF('day', asns.first_seen, asns.last_seen) + 1 as date_span
                FROM asn_stats asns
                LEFT JOIN volatile_asn_summary v ON asns.asn_name = v.asn_name
            )
            SELECT 
                asn_name,
                total_attacks,
                ROUND(avg_daily, 2) as avg_daily,
                active_days,
                countries,
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
            'asn_name': row[0],
            'total_attacks': row[1],
            'avg_daily': row[2],
            'active_days': row[3],
            'countries': row[4],
            'first_seen': row[5],
            'last_seen': row[6],
            'volatility': row[7],
            'max_daily': row[8],
            'date_span': row[9],
            'persistence_pct': row[10]
        } for row in result]
        
        return jsonify(data)