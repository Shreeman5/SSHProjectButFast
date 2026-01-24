"""
Username Attacks Volatile Endpoint
Chart 5 (Volatile mode): Most volatile usernames with filter support - FAST VERSION using pre-computed table
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_username_attacks_volatile(app):
    """Register volatile username attacks endpoint"""
    
    @app.route('/api/username_attacks_volatile', methods=['GET'])
    def get_username_attacks_volatile():
        """Chart 5 (Volatile): Most volatile usernames - uses pre-computed volatile_username_summary table"""
        start, end = parse_date_params()
        country_filter = request.args.get('country')
        asn_filter = request.args.get('asn')
        ip_filter = request.args.get('ip')
        username_filter = request.args.get('username')
        
        conn = get_db()
        
        if ip_filter:
            # Top 10 most volatile usernames for this IP (using pre-computed table)
            query = f"""
                WITH ip_usernames AS (
                    SELECT DISTINCT username
                    FROM daily_ip_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND IP = '{ip_filter}'
                ),
                top_volatile AS (
                    SELECT v.username, v.max_volatility
                    FROM volatile_username_summary v
                    INNER JOIN ip_usernames iu ON v.username = iu.username
                    ORDER BY v.max_volatility DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.username FROM date_range d CROSS JOIN top_volatile t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.username,
                    'Single IP' as country,
                    COALESCE(SUM(u.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(u.attacks)) OVER (PARTITION BY g.username ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(u.attacks), 0) - LAG(SUM(u.attacks)) OVER (PARTITION BY g.username ORDER BY g.date)) * 100.0 
                             / LAG(SUM(u.attacks)) OVER (PARTITION BY g.username ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_ip_username_attacks u
                    ON g.date = u.date AND g.username = u.username AND u.IP = '{ip_filter}'
                GROUP BY g.date, g.username
                ORDER BY g.date, attacks DESC
            """
        elif username_filter:
            # Single username - show its volatility
            query = f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    '{username_filter}' as username,
                    'Mixed' as country,
                    COALESCE(SUM(u.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(u.attacks)) OVER (ORDER BY d.date) > 0 
                        THEN ROUND(((COALESCE(SUM(u.attacks), 0) - LAG(SUM(u.attacks)) OVER (ORDER BY d.date)) * 100.0 
                             / LAG(SUM(u.attacks)) OVER (ORDER BY d.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM date_range d
                LEFT JOIN daily_ip_username_attacks u
                    ON d.date = u.date AND u.username = '{username_filter}'
                GROUP BY d.date
                ORDER BY d.date
            """
        elif asn_filter and country_filter:
            # Top 10 most volatile usernames for this ASN+Country (using pre-computed table)
            query = f"""
                WITH asn_country_usernames AS (
                    SELECT DISTINCT username
                    FROM daily_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' 
                      AND asn_name = '{asn_filter}' AND country = '{country_filter}'
                ),
                top_volatile AS (
                    SELECT v.username, v.max_volatility
                    FROM volatile_username_summary v
                    INNER JOIN asn_country_usernames acu ON v.username = acu.username
                    ORDER BY v.max_volatility DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.username FROM date_range d CROSS JOIN top_volatile t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.username,
                    '{country_filter}' as country,
                    COALESCE(SUM(u.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(u.attacks)) OVER (PARTITION BY g.username ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(u.attacks), 0) - LAG(SUM(u.attacks)) OVER (PARTITION BY g.username ORDER BY g.date)) * 100.0 
                             / LAG(SUM(u.attacks)) OVER (PARTITION BY g.username ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_username_attacks u
                    ON g.date = u.date AND g.username = u.username 
                    AND u.asn_name = '{asn_filter}' AND u.country = '{country_filter}'
                GROUP BY g.date, g.username
                ORDER BY g.date, attacks DESC
            """
        elif country_filter:
            # Top 10 most volatile usernames for this country (using pre-computed table)
            query = f"""
                WITH country_usernames AS (
                    SELECT DISTINCT username
                    FROM daily_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND country = '{country_filter}'
                ),
                top_volatile AS (
                    SELECT v.username, v.max_volatility
                    FROM volatile_username_summary v
                    INNER JOIN country_usernames cu ON v.username = cu.username
                    ORDER BY v.max_volatility DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.username FROM date_range d CROSS JOIN top_volatile t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.username,
                    '{country_filter}' as country,
                    COALESCE(u.attacks, 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(u.attacks) OVER (PARTITION BY g.username ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(u.attacks, 0) - LAG(u.attacks) OVER (PARTITION BY g.username ORDER BY g.date)) * 100.0 
                             / LAG(u.attacks) OVER (PARTITION BY g.username ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_username_attacks u ON g.date = u.date AND g.username = u.username AND u.country = '{country_filter}'
                ORDER BY g.date, attacks DESC
            """
        elif asn_filter:
            # Top 10 most volatile usernames for this ASN (using pre-computed table)
            query = f"""
                WITH asn_usernames AS (
                    SELECT DISTINCT username
                    FROM daily_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND asn_name = '{asn_filter}'
                ),
                top_volatile AS (
                    SELECT v.username, v.max_volatility
                    FROM volatile_username_summary v
                    INNER JOIN asn_usernames au ON v.username = au.username
                    ORDER BY v.max_volatility DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.username FROM date_range d CROSS JOIN top_volatile t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.username,
                    'Mixed' as country,
                    COALESCE(SUM(u.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(u.attacks)) OVER (PARTITION BY g.username ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(u.attacks), 0) - LAG(SUM(u.attacks)) OVER (PARTITION BY g.username ORDER BY g.date)) * 100.0 
                             / LAG(SUM(u.attacks)) OVER (PARTITION BY g.username ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_username_attacks u
                    ON g.date = u.date AND g.username = u.username AND u.asn_name = '{asn_filter}'
                GROUP BY g.date, g.username
                ORDER BY g.date, attacks DESC
            """
        else:
            # Top 10 most volatile usernames overall (using pre-computed table - FAST!)
            query = f"""
                WITH top_volatile AS (
                    SELECT username, max_volatility
                    FROM volatile_username_summary
                    ORDER BY max_volatility DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.username FROM date_range d CROSS JOIN top_volatile t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.username,
                    'Mixed' as country,
                    COALESCE(SUM(u.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(u.attacks)) OVER (PARTITION BY g.username ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(u.attacks), 0) - LAG(SUM(u.attacks)) OVER (PARTITION BY g.username ORDER BY g.date)) * 100.0 
                             / LAG(SUM(u.attacks)) OVER (PARTITION BY g.username ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_username_attacks u ON g.date = u.date AND g.username = u.username
                GROUP BY g.date, g.username
                ORDER BY g.date, attacks DESC
            """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{'date': row[0], 'username': row[1], 'country': row[2], 'attacks': row[3], 'pct_change': row[4]} for row in result]
        return jsonify(data)