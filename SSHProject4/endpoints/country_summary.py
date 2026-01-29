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
        limit = request.args.get('limit', type=int, default=None)
        offset = request.args.get('offset', type=int, default=0)
        
        conn = get_db()
        
        query = f"""
            WITH date_range AS (
                -- Generate all dates in the range
                SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
            ),
            country_list AS (
                -- Get all unique countries
                SELECT DISTINCT country
                FROM daily_country_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND country != 'Unknown'
            ),
            complete_grid AS (
                -- Create complete date x country grid
                SELECT d.date, c.country
                FROM date_range d
                CROSS JOIN country_list c
            ),
            daily_data AS (
                -- Join with actual data, filling missing days with 0
                SELECT 
                    g.date,
                    g.country,
                    COALESCE(d.attacks, 0) as attacks,
                    CASE WHEN d.attacks IS NOT NULL THEN 1 ELSE 0 END as was_present
                FROM complete_grid g
                LEFT JOIN daily_country_attacks d 
                    ON g.date = d.date AND g.country = d.country
            ),
            country_stats AS (
                SELECT 
                    country,
                    SUM(attacks) as total_attacks,
                    AVG(CASE WHEN was_present = 1 THEN attacks ELSE NULL END) as avg_daily,
                    SUM(was_present) as active_days,
                    MIN(CASE WHEN was_present = 1 THEN date ELSE NULL END) as first_seen,
                    MAX(CASE WHEN was_present = 1 THEN date ELSE NULL END) as last_seen,
                    MAX(attacks) as max_daily
                FROM daily_data
                GROUP BY country
            ),
            day_over_day AS (
                -- Calculate day-over-day changes for volatility metrics
                SELECT 
                    country,
                    date,
                    attacks,
                    attacks - LAG(attacks) OVER (PARTITION BY country ORDER BY date) as absolute_change,
                    CASE 
                        WHEN LAG(attacks) OVER (PARTITION BY country ORDER BY date) = 0 
                        THEN (attacks - 1.0) / 1.0 * 100  -- Use 1 as denominator when previous day was 0
                        ELSE (attacks - LAG(attacks) OVER (PARTITION BY country ORDER BY date)) 
                             / LAG(attacks) OVER (PARTITION BY country ORDER BY date) * 100
                    END as pct_change
                FROM daily_data
            ),
            volatility_metrics AS (
                SELECT 
                    country,
                    MAX(absolute_change) as max_absolute_change,
                    MAX(pct_change) as max_pct_change
                FROM day_over_day
                WHERE absolute_change IS NOT NULL  -- Skip first day which has no previous day
                GROUP BY country
            ),
            last_7_days AS (
                -- Calculate attacks in last 7 days
                SELECT 
                    country,
                    SUM(attacks) as recent_attacks
                FROM daily_data
                WHERE date > (SELECT MAX(date) FROM daily_data) - INTERVAL 7 DAY
                GROUP BY country
            ),
            total_days AS (
                -- Count total days in range
                SELECT COUNT(*) as total_day_count
                FROM date_range
            )
            SELECT 
                cs.country,
                cs.total_attacks,
                ROUND(cs.avg_daily, 2) as avg_daily,
                cs.first_seen::VARCHAR as first_seen,
                cs.last_seen::VARCHAR as last_seen,
                cs.max_daily,
                COALESCE(ROUND(vm.max_absolute_change, 2), 0) as max_absolute_change,
                COALESCE(ROUND(vm.max_pct_change, 2), 0) as max_pct_change,
                ROUND((cs.active_days::FLOAT / td.total_day_count) * 100, 1) as persistence_pct,
                COALESCE(l7.recent_attacks, 0) as recent_attacks,
                cs.active_days as active_days
            FROM country_stats cs
            CROSS JOIN total_days td
            LEFT JOIN volatility_metrics vm ON cs.country = vm.country
            LEFT JOIN last_7_days l7 ON cs.country = l7.country
            ORDER BY cs.total_attacks DESC
            {f'LIMIT {limit}' if limit else ''}
            {f'OFFSET {offset}' if offset > 0 else ''}
        """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{
            'country': row[0],
            'total_attacks': row[1],
            'avg_daily': row[2],
            'first_seen': row[3],
            'last_seen': row[4],
            'max_daily': row[5],
            'max_absolute_change': row[6],
            'max_pct_change': row[7],
            'persistence_pct': row[8],
            'recent_attacks': row[9],
            'active_days': row[10]
        } for row in result]
        
        return jsonify(data)