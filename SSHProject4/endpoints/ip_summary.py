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
            WITH date_range AS (
                -- Generate all dates in the range
                SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
            ),
            ip_list AS (
                -- Get all unique IPs
                SELECT DISTINCT IP
                FROM daily_ip_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
            ),
            complete_grid AS (
                -- Create complete date x IP grid
                SELECT d.date, i.IP
                FROM date_range d
                CROSS JOIN ip_list i
            ),
            daily_data AS (
                -- Join with actual data, filling missing days with 0
                SELECT 
                    g.date,
                    g.IP,
                    COALESCE(d.attacks, 0) as attacks,
                    d.country,
                    d.asn_name,
                    CASE WHEN d.attacks IS NOT NULL THEN 1 ELSE 0 END as was_present
                FROM complete_grid g
                LEFT JOIN daily_ip_attacks d 
                    ON g.date = d.date AND g.IP = d.IP
            ),
            ip_stats AS (
                SELECT 
                    IP,
                    SUM(attacks) as total_attacks,
                    AVG(CASE WHEN was_present = 1 THEN attacks ELSE NULL END) as avg_daily,
                    SUM(was_present) as active_days,
                    MIN(CASE WHEN was_present = 1 THEN date ELSE NULL END) as first_seen,
                    MAX(CASE WHEN was_present = 1 THEN date ELSE NULL END) as last_seen,
                    MAX(attacks) as max_daily,
                    MAX(country) as country,
                    MAX(asn_name) as asn_name
                FROM daily_data
                GROUP BY IP
            ),
            day_over_day AS (
                -- Calculate day-over-day changes for volatility metrics
                SELECT 
                    IP,
                    date,
                    attacks,
                    attacks - LAG(attacks) OVER (PARTITION BY IP ORDER BY date) as absolute_change,
                    CASE 
                        WHEN LAG(attacks) OVER (PARTITION BY IP ORDER BY date) = 0 
                        THEN (attacks - 1.0) / 1.0 * 100
                        ELSE (attacks - LAG(attacks) OVER (PARTITION BY IP ORDER BY date)) 
                             / LAG(attacks) OVER (PARTITION BY IP ORDER BY date) * 100
                    END as pct_change
                FROM daily_data
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
                -- Calculate attacks in last 7 days
                SELECT 
                    IP,
                    SUM(attacks) as recent_attacks
                FROM daily_data
                WHERE date > (SELECT MAX(date) FROM daily_data) - INTERVAL 7 DAY
                GROUP BY IP
            ),
            total_days AS (
                -- Count total days in range
                SELECT COUNT(*) as total_day_count
                FROM date_range
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
                ROUND((s.active_days::FLOAT / td.total_day_count) * 100, 1) as persistence_pct,
                COALESCE(l7.recent_attacks, 0) as recent_attacks,
                s.active_days as active_days,
                s.country,
                s.asn_name
            FROM ip_stats s
            CROSS JOIN total_days td
            LEFT JOIN volatility_metrics vm ON s.IP = vm.IP
            LEFT JOIN last_7_days l7 ON s.IP = l7.IP
            ORDER BY s.total_attacks DESC
        """
        
        result = conn.execute(query).fetchall()
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