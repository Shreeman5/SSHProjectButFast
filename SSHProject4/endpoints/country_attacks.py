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
        countries_filter = request.args.get('countries')  # Comma-separated list from discovery
        asn_filter = request.args.get('asn')
        asns_filter = request.args.get('asns')  # Comma-separated list from discovery
        ip_filter = request.args.get('ip')
        username_filter = request.args.get('username')
        
        conn = get_db()
        
        # Priority 1: Username filter - show top countries for this username
        if username_filter:
            where_conditions = [f"u.username = '{username_filter}'"]
            
            if ip_filter:
                where_conditions.append(f"u.IP = '{ip_filter}'")
            if asn_filter:
                where_conditions.append(f"u.asn_name = '{asn_filter}'")
            
            # Add country constraint (for discovery mode or single country)
            if country_filter:
                where_conditions.append(f"u.country = '{country_filter}'")
            elif countries_filter:
                countries = countries_filter.split(',')
                country_list = ', '.join([f"'{c.strip()}'" for c in countries])
                where_conditions.append(f"u.country IN ({country_list})")
            
            where_clause = " AND ".join(where_conditions)
            
            if country_filter:
                # Show specific country
                query = f"""
                    WITH date_range AS (
                        SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                    )
                    SELECT 
                        d.date::VARCHAR as date,
                        '{country_filter}' as country,
                        COALESCE(SUM(u.attacks), 0) as attacks
                    FROM date_range d
                    LEFT JOIN daily_ip_username_attacks u
                        ON d.date = u.date AND {where_clause}
                    GROUP BY d.date
                    ORDER BY d.date
                """
            else:
                # Show top countries for this username (within discovery countries if applicable)
                query = f"""
                    WITH top_countries AS (
                        SELECT country
                        FROM daily_ip_username_attacks u
                        WHERE date BETWEEN '{start}' AND '{end}' AND {where_clause}
                        GROUP BY country
                        ORDER BY SUM(u.attacks) DESC
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
                        ON g.date = u.date AND g.country = u.country AND {where_clause}
                    GROUP BY g.date, g.country
                    ORDER BY g.date, attacks DESC
                """
            result = conn.execute(query).fetchall()
        
        # Priority 2: IP filter - show top countries for this IP
        elif ip_filter:
            if country_filter:
                # Specific IP + specific country
                query = f"""
                    WITH date_range AS (
                        SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                    )
                    SELECT 
                        d.date::VARCHAR as date,
                        '{country_filter}' as country,
                        COALESCE(SUM(i.attacks), 0) as attacks
                    FROM date_range d
                    LEFT JOIN daily_ip_attacks i 
                        ON d.date = i.date AND i.IP = '{ip_filter}' AND i.country = '{country_filter}'
                    GROUP BY d.date
                    ORDER BY d.date
                """
            else:
                # IP selected: show top countries for this IP (within discovery countries if applicable)
                country_constraint = ""
                if countries_filter:
                    countries = countries_filter.split(',')
                    country_list = ', '.join([f"'{c.strip()}'" for c in countries])
                    country_constraint = f"AND country IN ({country_list})"
                
                query = f"""
                    WITH ip_countries AS (
                        SELECT country FROM daily_ip_attacks
                        WHERE date BETWEEN '{start}' AND '{end}' 
                          AND IP = '{ip_filter}'
                          {country_constraint}
                        GROUP BY country ORDER BY SUM(attacks) DESC LIMIT 10
                    ),
                    date_range AS (
                        SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                    ),
                    complete_grid AS (
                        SELECT d.date, t.country FROM date_range d CROSS JOIN ip_countries t
                    )
                    SELECT 
                        g.date::VARCHAR as date, g.country, COALESCE(SUM(i.attacks), 0) as attacks
                    FROM complete_grid g
                    LEFT JOIN daily_ip_attacks i
                        ON g.date = i.date AND g.country = i.country AND i.IP = '{ip_filter}'
                    GROUP BY g.date, g.country
                    ORDER BY g.date, attacks DESC
                """
            result = conn.execute(query).fetchall()
        
        # Priority 3: ASN filter - show top countries for this ASN
        elif asn_filter:
            if country_filter:
                # Specific ASN + specific country
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
            else:
                # ASN selected: show top 10 countries for this ASN (within discovery countries if applicable)
                country_constraint = ""
                if countries_filter:
                    countries = countries_filter.split(',')
                    country_list = ', '.join([f"'{c.strip()}'" for c in countries])
                    country_constraint = f"AND country IN ({country_list})"
                
                query = f"""
                    WITH asn_countries AS (
                        SELECT country FROM daily_asn_attacks
                        WHERE date BETWEEN '{start}' AND '{end}' 
                          AND asn_name = '{asn_filter}'
                          {country_constraint}
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
            result = conn.execute(query).fetchall()
        
        # Priority 3.5: ASNs filter - show top countries for those ASNs
        elif asns_filter:
            asns = asns_filter.split(',')
            asn_list = ', '.join([f"'{a.strip()}'" for a in asns])
            
            if country_filter:
                # Specific ASNs + specific country
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
                        ON d.date = a.date AND a.country = '{country_filter}' AND a.asn_name IN ({asn_list})
                    GROUP BY d.date
                    ORDER BY d.date
                """
            else:
                # ASNs selected: show top 10 countries for these ASNs
                query = f"""
                    WITH asn_countries AS (
                        SELECT country FROM daily_asn_attacks
                        WHERE date BETWEEN '{start}' AND '{end}' 
                          AND asn_name IN ({asn_list})
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
                        ON g.date = a.date AND g.country = a.country AND a.asn_name IN ({asn_list})
                    GROUP BY g.date, g.country
                    ORDER BY g.date, attacks DESC
                """
            result = conn.execute(query).fetchall()
        
        # Priority 4: Discovery mode countries (only when no other entity filter)
        elif countries_filter and not country_filter:
            countries = countries_filter.split(',')
            country_list = ', '.join([f"'{c.strip()}'" for c in countries])
            
            query = f"""
                WITH selected_countries AS (
                    SELECT unnest(ARRAY[{country_list}]) as country
                ),
                date_range AS (
                    SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE as date
                ),
                complete_grid AS (
                    SELECT d.date, s.country FROM date_range d CROSS JOIN selected_countries s
                )
                SELECT 
                    g.date::VARCHAR as date,
                    g.country,
                    COALESCE(c.attacks, 0) as attacks
                FROM complete_grid g
                LEFT JOIN daily_country_attacks c 
                    ON g.date = c.date AND g.country = c.country
                ORDER BY g.date, attacks DESC
            """
            result = conn.execute(query).fetchall()
        
        # Priority 5: Single country filter
        elif country_filter:
            query = f"""
                SELECT date::VARCHAR as date, country, attacks
                FROM daily_country_attacks
                WHERE date BETWEEN '{start}' AND '{end}' AND country = '{country_filter}'
                ORDER BY date
            """
            result = conn.execute(query).fetchall()
        
        # Priority 6: Default - show top 10 countries globally
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