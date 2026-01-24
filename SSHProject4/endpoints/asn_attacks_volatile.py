"""
ASN Attacks Volatile Endpoint
Chart 6 (Volatile mode): Most volatile ASNs with filter support - FAST VERSION using pre-computed table
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_asn_attacks_volatile(app):
    """Register volatile ASN attacks endpoint"""
    
    @app.route('/api/asn_attacks_volatile', methods=['GET'])
    def get_asn_attacks_volatile():
        """Chart 6 (Volatile): Most volatile ASNs - uses pre-computed volatile_asn_summary table"""
        start, end = parse_date_params()
        country_filter = request.args.get('country')
        asn_filter = request.args.get('asn')
        ip_filter = request.args.get('ip')
        username_filter = request.args.get('username')
        
        conn = get_db()
        
        if ip_filter:
            # Single IP's ASN - show its volatility
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
                    COALESCE(i.attacks, 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(i.attacks) OVER (ORDER BY d.date) > 0 
                        THEN ROUND(((COALESCE(i.attacks, 0) - LAG(i.attacks) OVER (ORDER BY d.date)) * 100.0 
                             / LAG(i.attacks) OVER (ORDER BY d.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM date_range d
                CROSS JOIN ip_asn
                LEFT JOIN daily_ip_attacks i ON d.date = i.date AND i.IP = '{ip_filter}'
                ORDER BY d.date
            """
        elif username_filter:
            # Top 10 most volatile ASNs for this username (using pre-computed table)
            query = f"""
                WITH username_asns AS (
                    SELECT DISTINCT asn_name
                    FROM daily_ip_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND username = '{username_filter}'
                ),
                top_volatile AS (
                    SELECT v.asn_name, v.max_volatility
                    FROM volatile_asn_summary v
                    INNER JOIN username_asns ua ON v.asn_name = ua.asn_name
                    ORDER BY v.max_volatility DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.asn_name FROM date_range d CROSS JOIN top_volatile t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.asn_name,
                    'Mixed' as country,
                    COALESCE(SUM(u.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(u.attacks)) OVER (PARTITION BY g.asn_name ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(u.attacks), 0) - LAG(SUM(u.attacks)) OVER (PARTITION BY g.asn_name ORDER BY g.date)) * 100.0 
                             / LAG(SUM(u.attacks)) OVER (PARTITION BY g.asn_name ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_ip_username_attacks u
                    ON g.date = u.date AND g.asn_name = u.asn_name AND u.username = '{username_filter}'
                GROUP BY g.date, g.asn_name
                ORDER BY g.date, attacks DESC
            """
        elif asn_filter and country_filter:
            # Single ASN+Country - show its volatility
            query = f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    '{asn_filter}' as asn_name,
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
                    ON d.date = a.date AND a.asn_name = '{asn_filter}' AND a.country = '{country_filter}'
                GROUP BY d.date
                ORDER BY d.date
            """
        elif asn_filter:
            # Single ASN - show its volatility
            query = f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    '{asn_filter}' as asn_name,
                    COALESCE(MAX(a.country), 'Mixed') as country,
                    COALESCE(SUM(a.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(a.attacks)) OVER (ORDER BY d.date) > 0 
                        THEN ROUND(((COALESCE(SUM(a.attacks), 0) - LAG(SUM(a.attacks)) OVER (ORDER BY d.date)) * 100.0 
                             / LAG(SUM(a.attacks)) OVER (ORDER BY d.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM date_range d
                LEFT JOIN daily_asn_attacks a ON d.date = a.date AND a.asn_name = '{asn_filter}'
                GROUP BY d.date
                ORDER BY d.date
            """
        elif country_filter:
            # Top 10 most volatile ASNs for this country (using pre-computed table)
            query = f"""
                WITH country_asns AS (
                    SELECT DISTINCT asn_name
                    FROM daily_asn_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND country = '{country_filter}'
                ),
                top_volatile AS (
                    SELECT v.asn_name, v.max_volatility
                    FROM volatile_asn_summary v
                    INNER JOIN country_asns ca ON v.asn_name = ca.asn_name
                    ORDER BY v.max_volatility DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.asn_name FROM date_range d CROSS JOIN top_volatile t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.asn_name,
                    '{country_filter}' as country,
                    COALESCE(SUM(a.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(a.attacks)) OVER (PARTITION BY g.asn_name ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(a.attacks), 0) - LAG(SUM(a.attacks)) OVER (PARTITION BY g.asn_name ORDER BY g.date)) * 100.0 
                             / LAG(SUM(a.attacks)) OVER (PARTITION BY g.asn_name ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_asn_attacks a
                    ON g.date = a.date AND g.asn_name = a.asn_name AND a.country = '{country_filter}'
                GROUP BY g.date, g.asn_name
                ORDER BY g.date, attacks DESC
            """
        else:
            # Top 10 most volatile ASNs overall (using pre-computed table - FAST!)
            query = f"""
                WITH top_volatile AS (
                    SELECT asn_name, max_volatility
                    FROM volatile_asn_summary
                    ORDER BY max_volatility DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.asn_name FROM date_range d CROSS JOIN top_volatile t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.asn_name,
                    'Mixed' as country,
                    COALESCE(SUM(a.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(a.attacks)) OVER (PARTITION BY g.asn_name ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(a.attacks), 0) - LAG(SUM(a.attacks)) OVER (PARTITION BY g.asn_name ORDER BY g.date)) * 100.0 
                             / LAG(SUM(a.attacks)) OVER (PARTITION BY g.asn_name ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_asn_attacks a ON g.date = a.date AND g.asn_name = a.asn_name
                GROUP BY g.date, g.asn_name
                ORDER BY g.date, attacks DESC
            """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{'date': row[0], 'asn_name': row[1], 'country': row[2], 'attacks': row[3], 'pct_change': row[4]} for row in result]
        return jsonify(data)