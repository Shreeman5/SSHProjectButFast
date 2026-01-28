"""
ASN Attacks Endpoint
Chart 6: Top ASNs with filter support
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_asn_attacks(app):
    """Register ASN attacks endpoint"""
    
    @app.route('/api/asn_attacks', methods=['GET'])
    def get_asn_attacks():
        """Chart 6: Top ASNs - with username filter support"""
        start, end = parse_date_params()
        country_filter = request.args.get('country')
        asn_filter = request.args.get('asn')
        ip_filter = request.args.get('ip')
        username_filter = request.args.get('username')
        
        conn = get_db()
        
        if username_filter:
            # Username filter takes priority - respect all other filters
            where_conditions = [f"u.username = '{username_filter}'"]
            
            if ip_filter:
                where_conditions.append(f"u.IP = '{ip_filter}'")
            if country_filter:
                where_conditions.append(f"u.country = '{country_filter}'")
            if asn_filter:
                where_conditions.append(f"u.asn_name = '{asn_filter}'")
            
            where_clause = " AND ".join(where_conditions)
            
            # If asn_filter is set, show only that ASN
            # Otherwise, show top ASNs for this username
            if asn_filter:
                query = f"""
                    WITH date_range AS (
                        SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                    )
                    SELECT 
                        d.date::VARCHAR as date,
                        '{asn_filter}' as asn_name,
                        COALESCE(MAX(u.country), 'Mixed') as country,
                        COALESCE(SUM(u.attacks), 0) as attacks
                    FROM date_range d
                    LEFT JOIN daily_ip_username_attacks u
                        ON d.date = u.date AND {where_clause}
                    GROUP BY d.date
                    ORDER BY d.date
                """
            else:
                query = f"""
                    WITH top_asns AS (
                        SELECT asn_name
                        FROM daily_ip_username_attacks u
                        WHERE date BETWEEN '{start}' AND '{end}' AND {where_clause}
                        GROUP BY asn_name
                        ORDER BY SUM(u.attacks) DESC
                        LIMIT 10
                    ),
                    date_range AS (
                        SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                    ),
                    complete_grid AS (
                        SELECT d.date, t.asn_name FROM date_range d CROSS JOIN top_asns t
                    )
                    SELECT 
                        g.date::VARCHAR as date,
                        g.asn_name,
                        'Mixed' as country,
                        COALESCE(SUM(u.attacks), 0) as attacks
                    FROM complete_grid g
                    LEFT JOIN daily_ip_username_attacks u
                        ON g.date = u.date AND g.asn_name = u.asn_name AND {where_clause}
                    GROUP BY g.date, g.asn_name
                    ORDER BY g.date, attacks DESC
                """
        elif ip_filter:
            query = f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                ip_asn AS (
                    SELECT DISTINCT asn_name, country FROM daily_ip_attacks WHERE IP = '{ip_filter}' LIMIT 1
                )
                SELECT 
                    d.date::VARCHAR as date,
                    COALESCE(i.asn_name, (SELECT asn_name FROM ip_asn)) as asn_name,
                    COALESCE(i.country, (SELECT country FROM ip_asn)) as country,
                    COALESCE(i.attacks, 0) as attacks
                FROM date_range d
                CROSS JOIN ip_asn
                LEFT JOIN daily_ip_attacks i ON d.date = i.date AND i.IP = '{ip_filter}'
                ORDER BY d.date
            """
        elif asn_filter and country_filter:
            query = f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    '{asn_filter}' as asn_name,
                    '{country_filter}' as country,
                    COALESCE(SUM(a.attacks), 0) as attacks
                FROM date_range d
                LEFT JOIN daily_asn_attacks a 
                    ON d.date = a.date AND a.asn_name = '{asn_filter}' AND a.country = '{country_filter}'
                GROUP BY d.date
                ORDER BY d.date
            """
        elif asn_filter:
            query = f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    '{asn_filter}' as asn_name,
                    COALESCE(MAX(a.country), 'Mixed') as country,
                    COALESCE(SUM(a.attacks), 0) as attacks
                FROM date_range d
                LEFT JOIN daily_asn_attacks a ON d.date = a.date AND a.asn_name = '{asn_filter}'
                GROUP BY d.date
                ORDER BY d.date
            """
        elif country_filter:
            query = f"""
                WITH top_asns AS (
                    SELECT asn_name
                    FROM daily_asn_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND country = '{country_filter}'
                    GROUP BY asn_name
                    ORDER BY SUM(attacks) DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.asn_name FROM date_range d CROSS JOIN top_asns t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.asn_name,
                    '{country_filter}' as country,
                    COALESCE(SUM(d.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_asn_attacks d 
                    ON g.date = d.date AND g.asn_name = d.asn_name AND d.country = '{country_filter}'
                GROUP BY g.date, g.asn_name
                ORDER BY g.date, attacks DESC
            """
        else:
            query = f"""
                WITH top_asns AS (
                    SELECT asn_name
                    FROM daily_asn_attacks
                    WHERE date BETWEEN '{start}' AND '{end}'
                    GROUP BY asn_name
                    ORDER BY SUM(attacks) DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.asn_name FROM date_range d CROSS JOIN top_asns t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.asn_name,
                    'Mixed' as country,
                    COALESCE(SUM(d.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_asn_attacks d ON g.date = d.date AND g.asn_name = d.asn_name
                GROUP BY g.date, g.asn_name
                ORDER BY g.date, attacks DESC
            """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{'date': row[0], 'asn_name': row[1], 'country': row[2], 'attacks': row[3]} for row in result]
        return jsonify(data)