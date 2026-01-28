"""
Total Attacks Endpoint
Chart 1: Total attacks over time with filter support
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_total_attacks(app):
    """Register total attacks endpoint"""
    
    @app.route('/api/total_attacks', methods=['GET'])
    def get_total_attacks():
        """Chart 1: Total attacks over time - with username filter support"""
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
            
            result = conn.execute(f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    COALESCE(SUM(u.attacks), 0) as attacks
                FROM date_range d
                LEFT JOIN daily_ip_username_attacks u
                    ON d.date = u.date AND {where_clause}
                GROUP BY d.date
                ORDER BY d.date
            """).fetchall()
        elif ip_filter:
            result = conn.execute(f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    COALESCE(SUM(i.attacks), 0) as attacks
                FROM date_range d
                LEFT JOIN daily_ip_attacks i ON d.date = i.date AND i.IP = '{ip_filter}'
                GROUP BY d.date
                ORDER BY d.date
            """).fetchall()
        elif asn_filter and country_filter:
            result = conn.execute(f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    COALESCE(SUM(a.attacks), 0) as attacks
                FROM date_range d
                LEFT JOIN daily_asn_attacks a
                    ON d.date = a.date AND a.asn_name = '{asn_filter}' AND a.country = '{country_filter}'
                GROUP BY d.date
                ORDER BY d.date
            """).fetchall()
        elif country_filter:
            result = conn.execute(f"""
                SELECT date::VARCHAR as date, attacks
                FROM daily_country_attacks
                WHERE date BETWEEN '{start}' AND '{end}' AND country = '{country_filter}'
                ORDER BY date
            """).fetchall()
        elif asn_filter:
            result = conn.execute(f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    COALESCE(SUM(a.attacks), 0) as attacks
                FROM date_range d
                LEFT JOIN daily_asn_attacks a ON d.date = a.date AND a.asn_name = '{asn_filter}'
                GROUP BY d.date
                ORDER BY d.date
            """).fetchall()
        else:
            result = conn.execute(f"""
                SELECT date::VARCHAR as date, total_attacks as attacks
                FROM daily_stats
                WHERE date BETWEEN '{start}' AND '{end}'
                ORDER BY date
            """).fetchall()
        
        conn.close()
        data = [{'date': row[0], 'attacks': row[1]} for row in result]
        return jsonify(data)