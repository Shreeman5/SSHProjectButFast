"""
IP Attacks Endpoint
Chart 4: Top IPs with filter support
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_ip_attacks(app):
    """Register IP attacks endpoint"""
    
    @app.route('/api/ip_attacks', methods=['GET'])
    def get_ip_attacks():
        """Chart 4: Top IPs - with username filter support"""
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
                )
                SELECT 
                    d.date::VARCHAR as date,
                    '{ip_filter}' as IP,
                    COALESCE(MAX(i.country), 'Unknown') as country,
                    COALESCE(SUM(i.attacks), 0) as attacks
                FROM date_range d
                LEFT JOIN daily_ip_attacks i ON d.date = i.date AND i.IP = '{ip_filter}'
                GROUP BY d.date
                ORDER BY d.date
            """
        elif username_filter:
            query = f"""
                WITH top_ips AS (
                    SELECT IP
                    FROM daily_ip_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND username = '{username_filter}'
                    GROUP BY IP
                    ORDER BY SUM(attacks) DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.IP FROM date_range d CROSS JOIN top_ips t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.IP,
                    COALESCE(MAX(u.country), 'Mixed') as country,
                    COALESCE(SUM(u.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_ip_username_attacks u
                    ON g.date = u.date AND g.IP = u.IP AND u.username = '{username_filter}'
                GROUP BY g.date, g.IP
                ORDER BY g.date, attacks DESC
            """
        elif asn_filter and country_filter:
            query = f"""
                WITH top_ips AS (
                    SELECT IP
                    FROM daily_ip_attacks
                    WHERE date BETWEEN '{start}' AND '{end}'
                      AND asn_name = '{asn_filter}' AND country = '{country_filter}'
                    GROUP BY IP
                    ORDER BY SUM(attacks) DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.IP FROM date_range d CROSS JOIN top_ips t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.IP,
                    COALESCE(MAX(i.country), '{country_filter}') as country,
                    COALESCE(SUM(i.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_ip_attacks i 
                    ON g.date = i.date AND g.IP = i.IP
                    AND i.asn_name = '{asn_filter}' AND i.country = '{country_filter}'
                GROUP BY g.date, g.IP
                ORDER BY g.date, attacks DESC
            """
        elif country_filter:
            query = f"""
                WITH top_ips AS (
                    SELECT IP
                    FROM daily_ip_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND country = '{country_filter}'
                    GROUP BY IP
                    ORDER BY SUM(attacks) DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.IP FROM date_range d CROSS JOIN top_ips t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.IP,
                    COALESCE(MAX(i.country), '{country_filter}') as country,
                    COALESCE(SUM(i.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_ip_attacks i 
                    ON g.date = i.date AND g.IP = i.IP AND i.country = '{country_filter}'
                GROUP BY g.date, g.IP
                ORDER BY g.date, attacks DESC
            """
        elif asn_filter:
            query = f"""
                WITH top_ips AS (
                    SELECT IP
                    FROM daily_ip_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND asn_name = '{asn_filter}'
                    GROUP BY IP
                    ORDER BY SUM(attacks) DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.IP FROM date_range d CROSS JOIN top_ips t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.IP,
                    COALESCE(MAX(i.country), 'Mixed') as country,
                    COALESCE(SUM(i.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_ip_attacks i 
                    ON g.date = i.date AND g.IP = i.IP AND i.asn_name = '{asn_filter}'
                GROUP BY g.date, g.IP
                ORDER BY g.date, attacks DESC
            """
        else:
            query = f"""
                WITH top_ips AS (
                    SELECT IP
                    FROM daily_ip_attacks
                    WHERE date BETWEEN '{start}' AND '{end}'
                    GROUP BY IP
                    ORDER BY SUM(attacks) DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.IP FROM date_range d CROSS JOIN top_ips t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.IP,
                    COALESCE(MAX(i.country), 'Mixed') as country,
                    COALESCE(SUM(i.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_ip_attacks i ON g.date = i.date AND g.IP = i.IP
                GROUP BY g.date, g.IP
                ORDER BY g.date, attacks DESC
            """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{'date': row[0], 'IP': row[1], 'country': row[2], 'attacks': row[3]} for row in result]
        return jsonify(data)
