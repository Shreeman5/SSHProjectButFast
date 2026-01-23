"""
Unusual Countries Endpoint
Chart 3: Most volatile countries with filter support
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_unusual_countries(app):
    """Register unusual countries endpoint"""
    
    @app.route('/api/unusual_countries', methods=['GET'])
    def get_unusual_countries():
        """Chart 3: Most Volatile Countries - with username filter support"""
        start, end = parse_date_params()
        country_filter = request.args.get('country')
        asn_filter = request.args.get('asn')
        ip_filter = request.args.get('ip')
        username_filter = request.args.get('username')
        
        conn = get_db()
        
        if ip_filter:
            query = f"""
                WITH ip_country AS (
                    SELECT DISTINCT country FROM daily_ip_attacks WHERE IP = '{ip_filter}' LIMIT 1
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    COALESCE(i.country, (SELECT country FROM ip_country)) as country,
                    COALESCE(i.attacks, 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(i.attacks) OVER (ORDER BY d.date) > 0 
                        THEN ROUND(((COALESCE(i.attacks, 0) - LAG(i.attacks) OVER (ORDER BY d.date)) * 100.0 
                             / LAG(i.attacks) OVER (ORDER BY d.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM date_range d
                CROSS JOIN ip_country
                LEFT JOIN daily_ip_attacks i ON d.date = i.date AND i.IP = '{ip_filter}'
                ORDER BY d.date
            """
        elif username_filter:
            query = f"""
                WITH username_daily AS (
                    SELECT 
                        country, date, SUM(attacks) as attacks,
                        LAG(SUM(attacks)) OVER (PARTITION BY country ORDER BY date) as prev_attacks
                    FROM daily_ip_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND username = '{username_filter}'
                    GROUP BY country, date
                ),
                pct_changes AS (
                    SELECT 
                        country, date, attacks, prev_attacks,
                        CASE WHEN prev_attacks > 0 THEN ((attacks - prev_attacks) * 100.0 / prev_attacks)
                        ELSE 0 END as pct_change
                    FROM username_daily
                    WHERE prev_attacks IS NOT NULL
                ),
                volatile_countries AS (
                    SELECT country, MAX(ABS(pct_change)) as max_pct_change
                    FROM pct_changes
                    GROUP BY country
                    ORDER BY max_pct_change DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, v.country FROM date_range d CROSS JOIN volatile_countries v
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.country,
                    COALESCE(SUM(u.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(u.attacks)) OVER (PARTITION BY g.country ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(u.attacks), 0) - LAG(SUM(u.attacks)) OVER (PARTITION BY g.country ORDER BY g.date)) * 100.0 
                             / LAG(SUM(u.attacks)) OVER (PARTITION BY g.country ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_ip_username_attacks u
                    ON g.date = u.date AND g.country = u.country AND u.username = '{username_filter}'
                GROUP BY g.date, g.country
                ORDER BY g.date, attacks DESC
            """
        elif asn_filter and country_filter:
            query = f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    '{country_filter}' as country,
                    COALESCE(SUM(a.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(a.attacks)) OVER (ORDER BY d.date) > 0 
                        THEN ROUND(((COALESCE(SUM(a.attacks), 0) - LAG(SUM(a.attacks)) OVER (ORDER BY d.date)) * 100.0 
                             / LAG(SUM(a.attacks)) OVER (ORDER BY d.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM date_range d
                LEFT JOIN daily_asn_attacks a
                    ON d.date = a.date AND a.country = '{country_filter}' AND a.asn_name = '{asn_filter}'
                GROUP BY d.date
                ORDER BY d.date
            """
        elif country_filter:
            query = f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    '{country_filter}' as country,
                    COALESCE(c.attacks, 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(c.attacks) OVER (ORDER BY d.date) > 0 
                        THEN ROUND(((COALESCE(c.attacks, 0) - LAG(c.attacks) OVER (ORDER BY d.date)) * 100.0 
                             / LAG(c.attacks) OVER (ORDER BY d.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM date_range d
                LEFT JOIN daily_country_attacks c ON d.date = c.date AND c.country = '{country_filter}'
                ORDER BY d.date
            """
        elif asn_filter:
            query = f"""
                WITH asn_daily_data AS (
                    SELECT 
                        country, date, SUM(attacks) as attacks,
                        LAG(SUM(attacks)) OVER (PARTITION BY country ORDER BY date) as prev_attacks
                    FROM daily_asn_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND asn_name = '{asn_filter}'
                    GROUP BY country, date
                ),
                pct_changes AS (
                    SELECT 
                        country, date, attacks, prev_attacks,
                        CASE WHEN prev_attacks > 0 THEN ((attacks - prev_attacks) * 100.0 / prev_attacks)
                        ELSE 0 END as pct_change
                    FROM asn_daily_data
                    WHERE prev_attacks IS NOT NULL
                ),
                volatile_countries AS (
                    SELECT country, MAX(ABS(pct_change)) as max_pct_change
                    FROM pct_changes
                    GROUP BY country
                    ORDER BY max_pct_change DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, v.country FROM date_range d CROSS JOIN volatile_countries v
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.country,
                    COALESCE(SUM(a.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(a.attacks)) OVER (PARTITION BY g.country ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(a.attacks), 0) - LAG(SUM(a.attacks)) OVER (PARTITION BY g.country ORDER BY g.date)) * 100.0 
                             / LAG(SUM(a.attacks)) OVER (PARTITION BY g.country ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_asn_attacks a
                    ON g.date = a.date AND g.country = a.country AND a.asn_name = '{asn_filter}'
                GROUP BY g.date, g.country
                ORDER BY g.date, attacks DESC
            """
        else:
            query = f"""
                WITH daily_data AS (
                    SELECT 
                        country, date, attacks,
                        LAG(attacks) OVER (PARTITION BY country ORDER BY date) as prev_attacks
                    FROM daily_country_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND country != 'Unknown'
                    ORDER BY country, date
                ),
                pct_changes AS (
                    SELECT 
                        country, date, attacks, prev_attacks,
                        CASE WHEN prev_attacks > 0 THEN ((attacks - prev_attacks) * 100.0 / prev_attacks)
                        ELSE 0 END as pct_change
                    FROM daily_data
                    WHERE prev_attacks IS NOT NULL
                ),
                volatile_countries AS (
                    SELECT country, MAX(ABS(pct_change)) as max_pct_change
                    FROM pct_changes
                    GROUP BY country
                    ORDER BY max_pct_change DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, v.country FROM date_range d CROSS JOIN volatile_countries v
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.country,
                    COALESCE(d.attacks, 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(d.attacks) OVER (PARTITION BY g.country ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(d.attacks, 0) - LAG(d.attacks) OVER (PARTITION BY g.country ORDER BY g.date)) * 100.0 
                             / LAG(d.attacks) OVER (PARTITION BY g.country ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_country_attacks d ON g.date = d.date AND g.country = d.country
                ORDER BY g.date, attacks DESC
            """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{'date': row[0], 'country': row[1], 'attacks': row[2], 'pct_change': row[3]} for row in result]
        return jsonify(data)
