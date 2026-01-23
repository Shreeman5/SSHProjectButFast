"""
Username Attacks Endpoint
Chart 5: Top usernames with filter support
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_username_attacks(app):
    """Register username attacks endpoint"""
    
    @app.route('/api/username_attacks', methods=['GET'])
    def get_username_attacks():
        """Chart 5: Top usernames - with username filter support"""
        start, end = parse_date_params()
        country_filter = request.args.get('country')
        asn_filter = request.args.get('asn')
        ip_filter = request.args.get('ip')
        username_filter = request.args.get('username')
        
        conn = get_db()
        
        if ip_filter:
            query = f"""
                WITH top_usernames AS (
                    SELECT username
                    FROM daily_ip_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND IP = '{ip_filter}'
                    GROUP BY username
                    ORDER BY SUM(attacks) DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.username FROM date_range d CROSS JOIN top_usernames t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.username,
                    'Single IP' as country,
                    COALESCE(SUM(d.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_ip_username_attacks d 
                    ON g.date = d.date AND g.username = d.username AND d.IP = '{ip_filter}'
                GROUP BY g.date, g.username
                ORDER BY g.date, attacks DESC
            """
        elif username_filter:
            # Show only this username - single line chart
            query = f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    '{username_filter}' as username,
                    'Mixed' as country,
                    COALESCE(SUM(u.attacks), 0) as attacks
                FROM date_range d
                LEFT JOIN daily_ip_username_attacks u
                    ON d.date = u.date AND u.username = '{username_filter}'
                GROUP BY d.date
                ORDER BY d.date
            """
        elif asn_filter and country_filter:
            query = f"""
                WITH top_usernames AS (
                    SELECT username
                    FROM daily_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}'
                      AND asn_name = '{asn_filter}' AND country = '{country_filter}'
                    GROUP BY username
                    ORDER BY SUM(attacks) DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.username FROM date_range d CROSS JOIN top_usernames t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.username,
                    '{country_filter}' as country,
                    COALESCE(SUM(d.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_username_attacks d 
                    ON g.date = d.date AND g.username = d.username
                    AND d.asn_name = '{asn_filter}' AND d.country = '{country_filter}'
                GROUP BY g.date, g.username
                ORDER BY g.date, attacks DESC
            """
        elif country_filter:
            query = f"""
                WITH top_usernames AS (
                    SELECT username
                    FROM daily_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND country = '{country_filter}'
                    GROUP BY username
                    ORDER BY SUM(attacks) DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.username FROM date_range d CROSS JOIN top_usernames t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.username,
                    '{country_filter}' as country,
                    COALESCE(SUM(d.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_username_attacks d 
                    ON g.date = d.date AND g.username = d.username AND d.country = '{country_filter}'
                GROUP BY g.date, g.username
                ORDER BY g.date, attacks DESC
            """
        elif asn_filter:
            query = f"""
                WITH top_usernames AS (
                    SELECT username
                    FROM daily_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND asn_name = '{asn_filter}'
                    GROUP BY username
                    ORDER BY SUM(attacks) DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.username FROM date_range d CROSS JOIN top_usernames t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.username,
                    'Mixed' as country,
                    COALESCE(SUM(d.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_username_attacks d 
                    ON g.date = d.date AND g.username = d.username AND d.asn_name = '{asn_filter}'
                GROUP BY g.date, g.username
                ORDER BY g.date, attacks DESC
            """
        else:
            query = f"""
                WITH top_usernames AS (
                    SELECT username
                    FROM daily_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}'
                    GROUP BY username
                    ORDER BY SUM(attacks) DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.username FROM date_range d CROSS JOIN top_usernames t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.username,
                    'Mixed' as country,
                    COALESCE(SUM(d.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_username_attacks d 
                    ON g.date = d.date AND g.username = d.username
                GROUP BY g.date, g.username
                ORDER BY g.date, attacks DESC
            """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{'date': row[0], 'username': row[1], 'country': row[2], 'attacks': row[3]} for row in result]
        return jsonify(data)
