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
        countries_filter = request.args.get('countries')  # Comma-separated list from discovery
        asn_filter = request.args.get('asn')
        asns_filter = request.args.get('asns')  # Comma-separated list from discovery
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
            # Username filter takes priority - respect all other filters
            print(f"\n🔍 DEBUG IP_ATTACKS with username_filter:")
            print(f"   username_filter: {username_filter}")
            print(f"   asns_filter: {asns_filter}")
            
            where_conditions = [f"u.username = '{username_filter}'"]
            
            if ip_filter:
                where_conditions.append(f"u.IP = '{ip_filter}'")
            if countries_filter:
                countries = countries_filter.split(',')
                country_list = ', '.join([f"'{c.strip()}'" for c in countries])
                where_conditions.append(f"u.country IN ({country_list})")
            elif country_filter:
                where_conditions.append(f"u.country = '{country_filter}'")
            
            # Add ASN constraint (single or multiple)
            if asn_filter:
                where_conditions.append(f"u.asn_name = '{asn_filter}'")
            elif asns_filter:
                asns = asns_filter.split('|||')
                print(f"   Split asns_filter into {len(asns)} ASNs")
                asn_list = ', '.join([f"'{a.strip()}'" for a in asns])
                where_conditions.append(f"u.asn_name IN ({asn_list})")
            
            where_clause = " AND ".join(where_conditions)
            print(f"   where_clause: {where_clause[:200]}...")
            
            # If ip_filter is set, show only that IP
            # Otherwise, show top IPs for this username
            if ip_filter:
                query = f"""
                    WITH date_range AS (
                        SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                    )
                    SELECT 
                        d.date::VARCHAR as date,
                        '{ip_filter}' as IP,
                        COALESCE(MAX(u.country), 'Unknown') as country,
                        COALESCE(SUM(u.attacks), 0) as attacks
                    FROM date_range d
                    LEFT JOIN daily_ip_username_attacks u
                        ON d.date = u.date AND {where_clause}
                    GROUP BY d.date
                    ORDER BY d.date
                """
            else:
                query = f"""
                    WITH top_ips AS (
                        SELECT IP
                        FROM daily_ip_username_attacks u
                        WHERE date BETWEEN '{start}' AND '{end}' AND {where_clause}
                        GROUP BY IP
                        ORDER BY SUM(u.attacks) DESC
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
                        ON g.date = u.date AND g.IP = u.IP AND {where_clause}
                    GROUP BY g.date, g.IP
                    ORDER BY g.date, attacks DESC
                """
        elif ip_filter:
            # Build country constraint for the IP filter
            country_where = ""
            if country_filter:
                country_where = f"AND i.country = '{country_filter}'"
            elif countries_filter:
                countries = countries_filter.split(',')
                country_list = ', '.join([f"'{c.strip()}'" for c in countries])
                country_where = f"AND i.country IN ({country_list})"
            
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
                LEFT JOIN daily_ip_attacks i ON d.date = i.date AND i.IP = '{ip_filter}' {country_where}
                GROUP BY d.date
                ORDER BY d.date
            """
        elif asns_filter:
            # Multiple ASNs from discovery - show top 10 IPs from those ASNs
            print(f"\n🔍 DEBUG IP_ATTACKS - asns_filter:")
            print(f"   Raw: {asns_filter}")
            asns = asns_filter.split('|||')
            print(f"   After split: {asns}")
            print(f"   Count: {len(asns)}")
            asn_list = ', '.join([f"'{a.strip()}'" for a in asns])
            print(f"   SQL list: {asn_list[:200]}...")
            
            # Add country constraint if present
            country_where = ""
            if country_filter:
                country_where = f"AND country = '{country_filter}'"
            elif countries_filter:
                countries = countries_filter.split(',')
                country_list = ', '.join([f"'{c.strip()}'" for c in countries])
                country_where = f"AND country IN ({country_list})"
            
            query = f"""
                WITH top_ips AS (
                    SELECT IP
                    FROM daily_ip_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' 
                      AND asn_name IN ({asn_list})
                      {country_where}
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
                    ON g.date = i.date AND g.IP = i.IP 
                    AND i.asn_name IN ({asn_list})
                    {country_where.replace('AND ', 'AND i.')}
                GROUP BY g.date, g.IP
                ORDER BY g.date, attacks DESC
            """
            print(f"   Query (first 300 chars): {query[:300]}...")
            result = conn.execute(query).fetchall()
            print(f"   Result count: {len(result)}")
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
                WITH top_ips AS (
                    SELECT IP
                    FROM daily_ip_attacks
                    WHERE date BETWEEN '{start}' AND '{end}' AND {country_where} {asn_where}
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
                    COALESCE(MAX(i.country), '{country_value}') as country,
                    COALESCE(SUM(i.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_ip_attacks i 
                    ON g.date = i.date AND g.IP = i.IP AND {country_where} {asn_where}
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