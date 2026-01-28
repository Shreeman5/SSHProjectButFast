"""
ASN Attacks Endpoint
Chart 6: Top ASNs with filter support + batch optimization
NO VOLATILITY - Just shows top attacking ASNs by volume
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_asn_attacks(app):
    """Register ASN attacks endpoint"""
    
    @app.route('/api/asn_attacks', methods=['GET'])
    def get_asn_attacks():
        """Chart 6: Top ASNs - with cascading filter support"""
        start, end = parse_date_params()
        
        # Single filters
        country_filter = request.args.get('country')
        asn_filter = request.args.get('asn')
        ip_filter = request.args.get('ip')
        username_filter = request.args.get('username')
        
        # Batch filters (plural)
        countries_filter = request.args.get('countries')
        asns_filter = request.args.get('asns')
        ips_filter = request.args.get('ips')
        usernames_filter = request.args.get('usernames')
        
        conn = get_db()
        
        # Build filter conditions
        where_conditions = []
        
        # Username filters
        if usernames_filter:
            usernames = usernames_filter.split('|||')
            username_list = ', '.join([f"'{u}'" for u in usernames])
            where_conditions.append(f"username IN ({username_list})")
        elif username_filter:
            where_conditions.append(f"username = '{username_filter}'")
        
        # IP filters
        if ips_filter:
            ips = ips_filter.split('|||')
            ip_list = ', '.join([f"'{ip}'" for ip in ips])
            where_conditions.append(f"IP IN ({ip_list})")
        elif ip_filter:
            where_conditions.append(f"IP = '{ip_filter}'")
        
        # ASN filters
        if asns_filter:
            asns = asns_filter.split('|||')
            asn_list = ', '.join([f"'{a}'" for a in asns])
            where_conditions.append(f"asn_name IN ({asn_list})")
        elif asn_filter:
            where_conditions.append(f"asn_name = '{asn_filter}'")
        
        # Country filters
        if countries_filter:
            countries = countries_filter.split('|||')
            country_list = ', '.join([f"'{c}'" for c in countries])
            where_conditions.append(f"country IN ({country_list})")
        elif country_filter:
            where_conditions.append(f"country = '{country_filter}'")
        
        # Determine which table to use
        use_username_table = username_filter or usernames_filter
        table = "daily_ip_username_attacks" if use_username_table else "daily_asn_attacks"
        table_alias = "u" if use_username_table else "a"
        
        # If specific ASN filter, show just that/those ASN(s)
        if asn_filter and not asns_filter:
            where_clause = " AND ".join([w for w in where_conditions if 'asn_name' not in w]) if len([w for w in where_conditions if 'asn_name' not in w]) > 0 else "1=1"
            
            query = f"""
                WITH date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                )
                SELECT 
                    d.date::VARCHAR as date,
                    '{asn_filter}' as asn_name,
                    COALESCE(MAX({table_alias}.country), 'Mixed') as country,
                    COALESCE(SUM({table_alias}.attacks), 0) as attacks
                FROM date_range d
                LEFT JOIN {table} {table_alias} 
                    ON d.date = {table_alias}.date 
                    AND {table_alias}.asn_name = '{asn_filter}'
                    {' AND ' + where_clause if where_clause != "1=1" else ''}
                GROUP BY d.date
                ORDER BY d.date
            """
        
        # If multiple specific ASNs, show those ASNs
        elif asns_filter:
            where_clause = " AND ".join([w for w in where_conditions if 'asn_name IN' not in w]) if len([w for w in where_conditions if 'asn_name IN' not in w]) > 0 else "1=1"
            asns = asns_filter.split('|||')
            asn_list = ', '.join([f"'{a}'" for a in asns])
            
            query = f"""
                WITH selected_asns AS (
                    SELECT unnest(ARRAY[{asn_list}]) as asn_name
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, s.asn_name FROM date_range d CROSS JOIN selected_asns s
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.asn_name,
                    COALESCE(MAX({table_alias}.country), 'Mixed') as country,
                    COALESCE(SUM({table_alias}.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN {table} {table_alias}
                    ON g.date = {table_alias}.date 
                    AND g.asn_name = {table_alias}.asn_name
                    {' AND ' + where_clause if where_clause != "1=1" else ''}
                GROUP BY g.date, g.asn_name
                ORDER BY g.date, attacks DESC
            """
        
        # Otherwise, show top 10 ASNs for the given filters
        else:
            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
            
            query = f"""
                WITH top_asns AS (
                    SELECT asn_name
                    FROM {table}
                    WHERE date BETWEEN '{start}' AND '{end}'
                      {' AND ' + where_clause if where_clause != "1=1" else ''}
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
                    COALESCE(MAX({table_alias}.country), 'Mixed') as country,
                    COALESCE(SUM({table_alias}.attacks), 0) as attacks
                FROM complete_grid g
                LEFT JOIN {table} {table_alias}
                    ON g.date = {table_alias}.date 
                    AND g.asn_name = {table_alias}.asn_name
                    {' AND ' + where_clause if where_clause != "1=1" else ''}
                GROUP BY g.date, g.asn_name
                ORDER BY g.date, attacks DESC
            """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{'date': row[0], 'asn_name': row[1], 'country': row[2], 'attacks': row[3]} for row in result]
        return jsonify(data)