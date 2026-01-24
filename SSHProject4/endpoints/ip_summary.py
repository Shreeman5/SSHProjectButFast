"""
IP Summary Endpoint
Returns comprehensive data for all IPs with discovery metrics
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_ip_summary(app):
    """Register IP summary endpoint for discovery tables"""
    
    @app.route('/api/ip_summary', methods=['GET'])
    def get_ip_summary():
        """Get comprehensive summary data for all IPs"""
        start, end = parse_date_params()
        
        conn = get_db()
        
        query = f"""
            WITH ip_stats AS (
                SELECT 
                    IP,
                    MAX(country) as country,
                    MAX(asn_name) as asn_name,
                    SUM(attacks) as total_attacks,
                    AVG(attacks) as avg_daily,
                    COUNT(DISTINCT date) as active_days,
                    MIN(date) as first_seen,
                    MAX(date) as last_seen,
                    MAX(attacks) as max_daily
                FROM daily_ip_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                GROUP BY IP
            ),
            with_volatility AS (
                SELECT 
                    ips.*,
                    COALESCE(v.max_volatility, 0) as volatility,
                    DATE_DIFF('day', ips.first_seen, ips.last_seen) + 1 as date_span
                FROM ip_stats ips
                LEFT JOIN volatile_ip_summary v ON ips.IP = v.IP
            )
            SELECT 
                IP,
                country,
                asn_name,
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
            'ip': row[0],
            'country': row[1],
            'asn_name': row[2],
            'total_attacks': row[3],
            'avg_daily': row[4],
            'active_days': row[5],
            'first_seen': row[6],
            'last_seen': row[7],
            'volatility': row[8],
            'max_daily': row[9],
            'date_span': row[10],
            'persistence_pct': row[11]
        } for row in result]
        
        return jsonify(data)