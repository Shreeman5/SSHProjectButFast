"""
IP Attacks Volatile Endpoint
Chart 4 (Volatile mode): Most volatile IPs with filter support - FAST VERSION using pre-computed table
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_ip_attacks_volatile(app):
    """Register volatile IP attacks endpoint"""
    
    @app.route('/api/ip_attacks_volatile', methods=['GET'])
    def get_ip_attacks_volatile():
        """Chart 4 (Volatile): Most volatile IPs - uses pre-computed volatile_ip_summary table"""
        start, end = parse_date_params()
        country_filter = request.args.get('country')
        asn_filter = request.args.get('asn')
        ip_filter = request.args.get('ip')
        username_filter = request.args.get('username')
        
        conn = get_db()
        
        if ip_filter:
            # Single IP - show its volatility
            query = f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    '{ip_filter}' as IP,
                    COALESCE(MAX(i.country), 'Unknown') as country,
                    COALESCE(SUM(i.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(i.attacks)) OVER (ORDER BY d.date) > 0 
                        THEN ROUND(((COALESCE(SUM(i.attacks), 0) - LAG(SUM(i.attacks)) OVER (ORDER BY d.date)) * 100.0 
                             / LAG(SUM(i.attacks)) OVER (ORDER BY d.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM date_range d
                LEFT JOIN daily_ip_attacks i ON d.date = i.date AND i.IP = '{ip_filter}'
                GROUP BY d.date
                ORDER BY d.date
            """
        elif username_filter:
            # Top 10 most volatile IPs for this username (using pre-computed table)
            query = f"""
                WITH username_ips AS (
                    SELECT DISTINCT IP
                    FROM daily_ip_username_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND username = '{username_filter}'
                ),
                top_volatile AS (
                    SELECT v.IP, v.max_volatility
                    FROM volatile_ip_summary v
                    INNER JOIN username_ips ui ON v.IP = ui.IP
                    ORDER BY v.max_volatility DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.IP FROM date_range d CROSS JOIN top_volatile t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.IP,
                    COALESCE(MAX(u.country), 'Mixed') as country,
                    COALESCE(SUM(u.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(u.attacks)) OVER (PARTITION BY g.IP ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(u.attacks), 0) - LAG(SUM(u.attacks)) OVER (PARTITION BY g.IP ORDER BY g.date)) * 100.0 
                             / LAG(SUM(u.attacks)) OVER (PARTITION BY g.IP ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_ip_username_attacks u
                    ON g.date = u.date AND g.IP = u.IP AND u.username = '{username_filter}'
                GROUP BY g.date, g.IP
                ORDER BY g.date, attacks DESC
            """
        elif asn_filter and country_filter:
            # Top 10 most volatile IPs for this ASN+Country (using pre-computed table)
            query = f"""
                WITH asn_country_ips AS (
                    SELECT DISTINCT IP
                    FROM daily_ip_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' 
                      AND asn_name = '{asn_filter}' AND country = '{country_filter}'
                ),
                top_volatile AS (
                    SELECT v.IP, v.max_volatility
                    FROM volatile_ip_summary v
                    INNER JOIN asn_country_ips aci ON v.IP = aci.IP
                    ORDER BY v.max_volatility DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.IP FROM date_range d CROSS JOIN top_volatile t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.IP,
                    '{country_filter}' as country,
                    COALESCE(SUM(i.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(i.attacks)) OVER (PARTITION BY g.IP ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(i.attacks), 0) - LAG(SUM(i.attacks)) OVER (PARTITION BY g.IP ORDER BY g.date)) * 100.0 
                             / LAG(SUM(i.attacks)) OVER (PARTITION BY g.IP ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_ip_attacks i
                    ON g.date = i.date AND g.IP = i.IP 
                    AND i.asn_name = '{asn_filter}' AND i.country = '{country_filter}'
                GROUP BY g.date, g.IP
                ORDER BY g.date, attacks DESC
            """
        elif country_filter:
            # Top 10 most volatile IPs for this country (using pre-computed table)
            query = f"""
                WITH country_ips AS (
                    SELECT DISTINCT IP
                    FROM daily_ip_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND country = '{country_filter}'
                ),
                top_volatile AS (
                    SELECT v.IP, v.max_volatility
                    FROM volatile_ip_summary v
                    INNER JOIN country_ips ci ON v.IP = ci.IP
                    ORDER BY v.max_volatility DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.IP FROM date_range d CROSS JOIN top_volatile t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.IP,
                    '{country_filter}' as country,
                    COALESCE(i.attacks, 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(i.attacks) OVER (PARTITION BY g.IP ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(i.attacks, 0) - LAG(i.attacks) OVER (PARTITION BY g.IP ORDER BY g.date)) * 100.0 
                             / LAG(i.attacks) OVER (PARTITION BY g.IP ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_ip_attacks i ON g.date = i.date AND g.IP = i.IP AND i.country = '{country_filter}'
                ORDER BY g.date, attacks DESC
            """
        elif asn_filter:
            # Top 10 most volatile IPs for this ASN (using pre-computed table)
            query = f"""
                WITH asn_ips AS (
                    SELECT DISTINCT IP
                    FROM daily_ip_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND asn_name = '{asn_filter}'
                ),
                top_volatile AS (
                    SELECT v.IP, v.max_volatility
                    FROM volatile_ip_summary v
                    INNER JOIN asn_ips ai ON v.IP = ai.IP
                    ORDER BY v.max_volatility DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.IP FROM date_range d CROSS JOIN top_volatile t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.IP,
                    COALESCE(MAX(i.country), 'Mixed') as country,
                    COALESCE(SUM(i.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(i.attacks)) OVER (PARTITION BY g.IP ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(i.attacks), 0) - LAG(SUM(i.attacks)) OVER (PARTITION BY g.IP ORDER BY g.date)) * 100.0 
                             / LAG(SUM(i.attacks)) OVER (PARTITION BY g.IP ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_ip_attacks i
                    ON g.date = i.date AND g.IP = i.IP AND i.asn_name = '{asn_filter}'
                GROUP BY g.date, g.IP
                ORDER BY g.date, attacks DESC
            """
        else:
            # Top 10 most volatile IPs overall (using pre-computed table - FAST!)
            query = f"""
                WITH top_volatile AS (
                    SELECT IP, max_volatility
                    FROM volatile_ip_summary
                    ORDER BY max_volatility DESC
                    LIMIT 10
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, t.IP FROM date_range d CROSS JOIN top_volatile t
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.IP,
                    COALESCE(MAX(i.country), 'Mixed') as country,
                    COALESCE(SUM(i.attacks), 0) as attacks,
                    COALESCE(
                        CASE WHEN LAG(SUM(i.attacks)) OVER (PARTITION BY g.IP ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(i.attacks), 0) - LAG(SUM(i.attacks)) OVER (PARTITION BY g.IP ORDER BY g.date)) * 100.0 
                             / LAG(SUM(i.attacks)) OVER (PARTITION BY g.IP ORDER BY g.date)), 2)
                        ELSE 0 END, 0
                    ) as pct_change
                FROM complete_grid g
                LEFT JOIN daily_ip_attacks i ON g.date = i.date AND g.IP = i.IP
                GROUP BY g.date, g.IP
                ORDER BY g.date, attacks DESC
            """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{'date': row[0], 'IP': row[1], 'country': row[2], 'attacks': row[3], 'pct_change': row[4]} for row in result]
        return jsonify(data)