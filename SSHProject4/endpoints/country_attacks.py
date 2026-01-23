"""
Country Attacks Endpoint
Chart 2: Top countries with filter support
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_country_attacks(app):
    """Register country attacks endpoint"""
    
    @app.route('/api/country_attacks', methods=['GET'])
    def get_country_attacks():
        """Chart 2: Top countries - with username filter support"""
        start, end = parse_date_params()
        country_filter = request.args.get('country')
        asn_filter = request.args.get('asn')
        ip_filter = request.args.get('ip')
        username_filter = request.args.get('username')
        
        conn = get_db()
        
        if ip_filter:
            query = f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                ip_country AS (
                    SELECT DISTINCT country FROM daily_ip_attacks WHERE IP = '{ip_filter}' LIMIT 1
                )
                SELECT 
                    d.date::VARCHAR as date,
                    COALESCE(i.country, (SELECT country FROM ip_country)) as country,
                    COALESCE(i.attacks, 0) as attacks
                FROM date_range d
                CROSS JOIN ip_country
                LEFT JOIN daily_ip_attacks i ON d.date = i.date AND i.IP = '{ip_filter}'
                ORDER BY d.date
            """
        elif username_filter:
            query = f"""
                WITH top_countries AS (
                    SELECT country
                    FROM daily_ip_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND username = '{username_filter}'
                    GROUP BY country
                    ORDER BY SUM(attacks) DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.country FROM date_range d CROSS JOIN top_countries t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.country,
                    COALESCE(SUM(u.attacks), 0) as attacks
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
                    COALESCE(SUM(a.attacks), 0) as attacks
                FROM date_range d
                LEFT JOIN daily_asn_attacks a
                    ON d.date = a.date AND a.country = '{country_filter}' AND a.asn_name = '{asn_filter}'
                GROUP BY d.date
                ORDER BY d.date
            """
        elif country_filter:
            query = f"""
                SELECT date::VARCHAR as date, country, attacks
                FROM daily_country_attacks
                WHERE date BETWEEN '{start}' AND '{end}' AND country = '{country_filter}'
                ORDER BY date
            """
        elif asn_filter:
            query = f"""
                WITH asn_countries AS (
                    SELECT country FROM daily_asn_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND asn_name = '{asn_filter}'
                    GROUP BY country ORDER BY SUM(attacks) DESC LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.country FROM date_range d CROSS JOIN asn_countries t
                )
                SELECT 
                    g.date::VARCHAR as date, g.country, COALESCE(SUM(a.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_asn_attacks a
                    ON g.date = a.date AND g.country = a.country AND a.asn_name = '{asn_filter}'
                GROUP BY g.date, g.country
                ORDER BY g.date, attacks DESC
            """
        else:
            query = f"""
                WITH top_countries AS (
                    SELECT country FROM daily_country_attacks
                    WHERE date BETWEEN '{start}' AND '{end}'
                    GROUP BY country ORDER BY SUM(attacks) DESC LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.country FROM date_range d CROSS JOIN top_countries t
                )
                SELECT 
                    g.date::VARCHAR as date, g.country, COALESCE(d.attacks, 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_country_attacks d ON g.date = d.date AND g.country = d.country
                ORDER BY g.date, attacks DESC
            """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{'date': row[0], 'country': row[1], 'attacks': row[2]} for row in result]
        return jsonify(data)
