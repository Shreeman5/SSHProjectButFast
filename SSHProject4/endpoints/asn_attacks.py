"""
ASN Attacks Endpoint - FIXED VERSION
Chart 6: Top ASNs with proper multi-filter support
FIXES: Respects ALL active filters together (country + ASN + IP + username)
BUG FIX: When ASN filter is active, don't include it in where_clause to avoid conflicts
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params


def register_asn_attacks(app):
    """Register ASN attacks endpoint"""
    
    @app.route('/api/asn_attacks', methods=['GET'])
    def get_asn_attacks():
        """Chart 6: Top ASNs - respects ALL active filters"""
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
        
        # Determine which table to use
        use_username_table = username_filter or usernames_filter
        use_ip_table = ip_filter or ips_filter or use_username_table
        
        if use_username_table:
            table = "daily_ip_username_attacks"
            table_alias = "t"
        elif use_ip_table:
            table = "daily_ip_attacks"
            table_alias = "t"
        else:
            table = "daily_asn_attacks"
            table_alias = "t"
        
        # Build filter conditions dynamically
        # NOTE: We build TWO where clauses:
        # 1. where_clause_with_asn: includes ALL filters (for top 10 query)
        # 2. where_clause_without_asn: excludes ASN filter (for specific ASN query)
        
        where_conditions_with_asn = []
        where_conditions_without_asn = []
        
        # Username filter
        if usernames_filter:
            usernames = usernames_filter.split('|||')
            username_list = ', '.join([f"'{u}'" for u in usernames])
            condition = f"username IN ({username_list})"
            where_conditions_with_asn.append(condition)
            where_conditions_without_asn.append(condition)
        elif username_filter:
            condition = f"username = '{username_filter}'"
            where_conditions_with_asn.append(condition)
            where_conditions_without_asn.append(condition)
        
        # IP filter
        if ips_filter:
            ips = ips_filter.split('|||')
            ip_list = ', '.join([f"'{ip}'" for ip in ips])
            condition = f"IP IN ({ip_list})"
            where_conditions_with_asn.append(condition)
            where_conditions_without_asn.append(condition)
        elif ip_filter:
            condition = f"IP = '{ip_filter}'"
            where_conditions_with_asn.append(condition)
            where_conditions_without_asn.append(condition)
        
        # ASN filter - ONLY add to where_conditions_with_asn
        if asns_filter:
            asns = asns_filter.split('|||')
            asn_list = ', '.join([f"'{a}'" for a in asns])
            where_conditions_with_asn.append(f"asn_name IN ({asn_list})")
        elif asn_filter:
            where_conditions_with_asn.append(f"asn_name = '{asn_filter}'")
        
        # Country filter
        if countries_filter:
            countries = countries_filter.split('|||')
            country_list = ', '.join([f"'{c}'" for c in countries])
            condition = f"country IN ({country_list})"
            where_conditions_with_asn.append(condition)
            where_conditions_without_asn.append(condition)
        elif country_filter:
            condition = f"country = '{country_filter}'"
            where_conditions_with_asn.append(condition)
            where_conditions_without_asn.append(condition)
        
        where_clause_with_asn = " AND ".join(where_conditions_with_asn) if where_conditions_with_asn else "1=1"
        where_clause_without_asn = " AND ".join(where_conditions_without_asn) if where_conditions_without_asn else "1=1"
        
        # If specific ASN filter(s), show only those ASN(s)
        if asn_filter or asns_filter:
            if asns_filter:
                asns = asns_filter.split('|||')
                asn_list = ', '.join([f"'{a}'" for a in asns])
                asn_values = asns
            else:
                asn_list = f"'{asn_filter}'"
                asn_values = [asn_filter]
            
            # Build query for specific ASN(s) with ALL filters EXCEPT ASN
            # (ASN is already constrained by the complete_grid)
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
                    AND {where_clause_without_asn}
                GROUP BY g.date, g.asn_name
                ORDER BY g.date
            """
        else:
            # Show top 10 ASNs with ALL filters applied
            query = f"""
                WITH top_asns AS (
                    SELECT asn_name
                    FROM {table}
                    WHERE date BETWEEN '{start}' AND '{end}' AND {where_clause_with_asn}
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
                    AND {where_clause_with_asn}
                GROUP BY g.date, g.asn_name
                ORDER BY g.date, attacks DESC
            """
        
        result = conn.execute(query).fetchall()
        conn.close()
        
        data = [{'date': row[0], 'asn_name': row[1], 'country': row[2], 'attacks': row[3]} for row in result]
        return jsonify(data)