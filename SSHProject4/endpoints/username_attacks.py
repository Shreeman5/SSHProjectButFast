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
        countries_filter = request.args.get('countries')  # Comma-separated list from discovery
        asn_filter = request.args.get('asn')
        ip_filter = request.args.get('ip')
        username_filter = request.args.get('username')
        
        # Determine country condition for queries
        if countries_filter:
            countries = countries_filter.split(',')
            country_list = ', '.join([f"'{c.strip()}'" for c in countries])
            country_condition = f"country IN ({country_list})"
            country_value = 'Mixed'
        elif country_filter:
            country_condition = f"country = '{country_filter}'"
            country_value = country_filter
        else:
            country_condition = None
            country_value = 'Mixed'
        
        conn = get_db()
        
        if username_filter:
            # Show only this username - single line chart, respecting all other filters
            where_conditions = [f"u.username = '{username_filter}'"]
            
            if ip_filter:
                where_conditions.append(f"u.IP = '{ip_filter}'")
            
            # Add country constraint (single or multiple)
            if country_filter:
                where_conditions.append(f"u.country = '{country_filter}'")
            elif countries_filter:
                countries = countries_filter.split(',')
                country_list = ', '.join([f"'{c.strip()}'" for c in countries])
                where_conditions.append(f"u.country IN ({country_list})")
            
            if asn_filter:
                where_conditions.append(f"u.asn_name = '{asn_filter}'")
            
            where_clause = " AND ".join(where_conditions)
            
            query = f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    '{username_filter}' as username,
                    COALESCE(MAX(u.country), 'Mixed') as country,
                    COALESCE(SUM(u.attacks), 0) as attacks
                FROM date_range d
                LEFT JOIN daily_ip_username_attacks u
                    ON d.date = u.date AND {where_clause}
                GROUP BY d.date
                ORDER BY d.date
            """
        elif ip_filter:
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
        elif country_filter or countries_filter:
            if countries_filter:
                countries = countries_filter.split(',')
                country_list = ', '.join([f"'{c.strip()}'" for c in countries])
                country_where = f"country IN ({country_list})"
                asn_where = f"AND asn_name = '{asn_filter}'" if asn_filter else ""
            else:
                country_where = f"country = '{country_filter}'"
                asn_where = f"AND asn_name = '{asn_filter}'" if asn_filter else ""
            
            query = f"""
                WITH top_usernames AS (
                    SELECT username
                    FROM daily_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND {country_where} {asn_where}
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
                    '{country_value}' as country,
                    COALESCE(SUM(d.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_username_attacks d 
                    ON g.date = d.date AND g.username = d.username AND {country_where} {asn_where}
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