"""
Username Summary Endpoint
Returns comprehensive data for all usernames with discovery metrics
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_username_summary(app):
    """Register username summary endpoint for discovery tables"""
    
    @app.route('/api/username_summary', methods=['GET'])
    def get_username_summary():
        """Get comprehensive summary data for all usernames"""
        start, end = parse_date_params()
        
        conn = get_db()
        
        query = f"""
            WITH date_range AS (
                -- Generate all dates in the range
                SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
            ),
            username_list AS (
                -- Get all unique usernames
                SELECT DISTINCT username
                FROM daily_username_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
            ),
            complete_grid AS (
                -- Create complete date x username grid
                SELECT d.date, u.username
                FROM date_range d
                CROSS JOIN username_list u
            ),
            daily_data AS (
                -- Join with actual data, filling missing days with 0
                SELECT 
                    g.date,
                    g.username,
                    COALESCE(d.attacks, 0) as attacks,
                    d.country,
                    CASE WHEN d.attacks IS NOT NULL THEN 1 ELSE 0 END as was_present
                FROM complete_grid g
                LEFT JOIN daily_username_attacks d 
                    ON g.date = d.date AND g.username = d.username
            ),
            username_stats AS (
                SELECT 
                    username,
                    SUM(attacks) as total_attacks,
                    AVG(CASE WHEN was_present = 1 THEN attacks ELSE NULL END) as avg_daily,
                    SUM(was_present) as active_days,
                    MIN(CASE WHEN was_present = 1 THEN date ELSE NULL END) as first_seen,
                    MAX(CASE WHEN was_present = 1 THEN date ELSE NULL END) as last_seen,
                    MAX(attacks) as max_daily,
                    COUNT(DISTINCT country) as country_count
                FROM daily_data
                GROUP BY username
            ),
            day_over_day AS (
                -- Calculate day-over-day changes for volatility metrics
                SELECT 
                    username,
                    date,
                    attacks,
                    attacks - LAG(attacks) OVER (PARTITION BY username ORDER BY date) as absolute_change,
                    CASE 
                        WHEN LAG(attacks) OVER (PARTITION BY username ORDER BY date) = 0 
                        THEN (attacks - 1.0) / 1.0 * 100
                        ELSE (attacks - LAG(attacks) OVER (PARTITION BY username ORDER BY date)) 
                             / LAG(attacks) OVER (PARTITION BY username ORDER BY date) * 100
                    END as pct_change
                FROM daily_data
            ),
            volatility_metrics AS (
                SELECT 
                    username,
                    MAX(absolute_change) as max_absolute_change,
                    MAX(pct_change) as max_pct_change
                FROM day_over_day
                WHERE absolute_change IS NOT NULL
                GROUP BY username
            ),
            last_7_days AS (
                -- Calculate attacks in last 7 days
                SELECT 
                    username,
                    SUM(attacks) as recent_attacks
                FROM daily_data
                WHERE date > (SELECT MAX(date) FROM daily_data) - INTERVAL 7 DAY
                GROUP BY username
            ),
            total_days AS (
                -- Count total days in range
                SELECT COUNT(*) as total_day_count
                FROM date_range
            )
            SELECT 
                s.username,
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
                s.country_count
            FROM username_stats s
            CROSS JOIN total_days td
            LEFT JOIN volatility_metrics vm ON s.username = vm.username
            LEFT JOIN last_7_days l7 ON s.username = l7.username
            ORDER BY s.total_attacks DESC
        """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{
            'username': row[0],
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
            'countries': row[11]
        } for row in result]
        
        return jsonify(data)