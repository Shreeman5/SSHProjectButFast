"""
IP Summary Endpoint - OPTIMIZED
Returns comprehensive data for all IPs with discovery metrics
Uses simpler aggregation without complete grid for better performance
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_ip_summary(app):
    """Register IP summary endpoint for discovery tables"""
    
    @app.route('/api/ip_count', methods=['GET'])
    def get_ip_count():
        """Get total count of unique IPs (for debugging)"""
        start, end = parse_date_params()
        conn = get_db()
        query = f"""
            SELECT COUNT(DISTINCT IP) as total
            FROM daily_ip_attacks
            WHERE date BETWEEN '{start}' AND '{end}'
        """
        result = conn.execute(query).fetchone()
        conn.close()
        total = result[0]
        print(f"[IP_COUNT] Total unique IPs: {total:,}")
        return jsonify({'total_ips': total, 'date_range': {'start': start, 'end': end}})
    
    @app.route('/api/ip_summary', methods=['GET'])
    def get_ip_summary():
        """Get comprehensive summary data for all IPs"""
        start, end = parse_date_params()
        limit = request.args.get('limit', type=int, default=1000)
        offset = request.args.get('offset', type=int, default=0)
        
        conn = get_db()
        
        # Step 1: Get the top N IPs by total attacks
        top_query = f"""
            SELECT IP
            FROM daily_ip_attacks
            WHERE date BETWEEN '{start}' AND '{end}'
            GROUP BY IP
            ORDER BY SUM(attacks) DESC
            LIMIT {limit}
            OFFSET {offset}
        """
        
        top_result = conn.execute(top_query).fetchall()
        
        if not top_result:
            conn.close()
            return jsonify([])
        
        # Get list of IPs
        ips = [row[0] for row in top_result]
        
        # Create placeholder string for parameterized query
        placeholders = ', '.join(['?' for _ in ips])
        
        # Step 2: Calculate stats only for these IPs
        stats_query = f"""
            WITH ip_stats AS (
                SELECT 
                    IP,
                    SUM(attacks) as total_attacks,
                    AVG(attacks) as avg_daily,
                    COUNT(DISTINCT date) as active_days,
                    MIN(date) as first_seen,
                    MAX(date) as last_seen,
                    MAX(attacks) as max_daily,
                    MODE() WITHIN GROUP (ORDER BY country) as most_common_country,
                    MODE() WITHIN GROUP (ORDER BY asn_name) as most_common_asn
                FROM daily_ip_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND IP IN ({placeholders})
                GROUP BY IP
            ),
            day_over_day AS (
                SELECT 
                    IP,
                    attacks - LAG(attacks) OVER (PARTITION BY IP ORDER BY date) as absolute_change,
                    CASE 
                        WHEN LAG(attacks) OVER (PARTITION BY IP ORDER BY date) = 0 
                        THEN (attacks - 1.0) / 1.0 * 100
                        ELSE (attacks - LAG(attacks) OVER (PARTITION BY IP ORDER BY date)) 
                             / LAG(attacks) OVER (PARTITION BY IP ORDER BY date) * 100
                    END as pct_change
                FROM daily_ip_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND IP IN ({placeholders})
            ),
            volatility_metrics AS (
                SELECT 
                    IP,
                    MAX(absolute_change) as max_absolute_change,
                    MAX(pct_change) as max_pct_change
                FROM day_over_day
                WHERE absolute_change IS NOT NULL
                GROUP BY IP
            ),
            last_7_days AS (
                SELECT 
                    IP,
                    SUM(attacks) as recent_attacks
                FROM daily_ip_attacks
                WHERE date BETWEEN (DATE '{end}' - INTERVAL 6 DAY) AND DATE '{end}'
                  AND IP IN ({placeholders})
                GROUP BY IP
            )
            SELECT 
                s.IP,
                s.total_attacks,
                ROUND(s.avg_daily, 2) as avg_daily,
                s.first_seen::VARCHAR as first_seen,
                s.last_seen::VARCHAR as last_seen,
                s.max_daily,
                COALESCE(ROUND(vm.max_absolute_change, 2), 0) as max_absolute_change,
                COALESCE(ROUND(vm.max_pct_change, 2), 0) as max_pct_change,
                ROUND((s.active_days::FLOAT / 69.0) * 100, 1) as persistence_pct,
                COALESCE(l7.recent_attacks, 0) as recent_attacks,
                s.active_days,
                s.most_common_country as country,
                s.most_common_asn as asn_name
            FROM ip_stats s
            LEFT JOIN volatility_metrics vm ON s.IP = vm.IP
            LEFT JOIN last_7_days l7 ON s.IP = l7.IP
            ORDER BY s.total_attacks DESC
        """
        
        # Execute with parameters (repeat IPs for each IN clause)
        params = ips + ips + ips  # 3 IN clauses
        result = conn.execute(stats_query, params).fetchall()
        conn.close()
        
        data = [{
            'ip': row[0],
            'total_attacks': row[1],
            'avg_daily': row[2],
            'first_seen': row[3],
            'last_seen': row[4],
            'max_daily': row[5],
            'max_absolute_change': row[6],
            'max_pct_change': row[7],
            'persistence_pct': row[8],
            'recent_attacks': row[9],
            'active_days': row[10],
            'country': row[11],
            'asn_name': row[12]
        } for row in result]
        
        return jsonify(data)