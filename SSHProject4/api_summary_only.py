#!/usr/bin/env python3
"""
Flask API for Attack Data Visualizations
ONLY uses summary tables - never touches the attacks view
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import duckdb
import configparser
from pathlib import Path

app = Flask(__name__)
CORS(app)

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')
DB_PATH = config['paths']['duckdb_path']

def get_db():
    """Get database connection"""
    return duckdb.connect(str(DB_PATH), read_only=True)

def parse_date_params():
    """Parse date range from query parameters"""
    start = request.args.get('start', '2022-11-01')
    end = request.args.get('end', '2023-01-08')
    return start, end


@app.route('/api/total_attacks', methods=['GET'])
def get_total_attacks():
    """Chart 1: Total attacks over time - uses daily_stats"""
    start, end = parse_date_params()
    
    conn = get_db()
    
    query = f"""
        SELECT 
            date::VARCHAR as date,
            total_attacks as attacks
        FROM daily_stats
        WHERE date BETWEEN '{start}' AND '{end}'
        ORDER BY date
    """
    
    result = conn.execute(query).fetchall()
    conn.close()
    
    # Convert to list of dicts
    data = [{'date': row[0], 'attacks': row[1]} for row in result]
    
    return jsonify(data)


"""
Updated API Endpoints with Zero-Filling
Replace these 5 functions in api_summary_only.py

This fixes the "disappearing line" issue where lines vanish when a value is 0 for a day.
All charts will now show continuous lines even when attacks = 0 on certain days.
"""

# ============================================================================
# 1. Country Attacks - WITH ZERO-FILLING
# ============================================================================
# ============================================================================
# UPDATED /api/country_attacks endpoint - ADD IP FILTER
# Replace in api_summary_only.py
# ============================================================================

@app.route('/api/country_attacks', methods=['GET'])
def get_country_attacks():
    """Chart 2: Top 20 countries - with zero-filling and IP filter"""
    start, end = parse_date_params()
    country_filter = request.args.get('country')
    asn_filter = request.args.get('asn')
    ip_filter = request.args.get('ip')  # ← NEW
    
    conn = get_db()
    
    if ip_filter:
        # Filter by IP - show which country this IP is from
        query = f"""
            WITH date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            ),
            ip_country AS (
                SELECT DISTINCT country
                FROM daily_ip_attacks
                WHERE IP = '{ip_filter}'
                LIMIT 1
            )
            SELECT 
                d.date::VARCHAR as date,
                COALESCE(i.country, (SELECT country FROM ip_country)) as country,
                COALESCE(i.attacks, 0) as attacks
            FROM date_range d
            CROSS JOIN ip_country
            LEFT JOIN daily_ip_attacks i
                ON d.date = i.date
                AND i.IP = '{ip_filter}'
            ORDER BY d.date
        """
    elif country_filter:
        # Single country, no zero-filling needed
        query = f"""
            SELECT 
                date::VARCHAR as date,
                country,
                attacks
            FROM daily_country_attacks
            WHERE date BETWEEN '{start}' AND '{end}'
              AND country = '{country_filter}'
            ORDER BY date
        """
    elif asn_filter:
        # Filter by ASN - show which countries this ASN operates in
        query = f"""
            WITH asn_countries AS (
                SELECT country
                FROM daily_asn_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND asn_name = '{asn_filter}'
                GROUP BY country
                ORDER BY SUM(attacks) DESC
                LIMIT 10
            ),
            date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            ),
            complete_grid AS (
                SELECT d.date, t.country
                FROM date_range d
                CROSS JOIN asn_countries t
            )
            SELECT 
                g.date::VARCHAR as date,
                g.country,
                COALESCE(SUM(a.attacks), 0) as attacks
            FROM complete_grid g
            LEFT JOIN daily_asn_attacks a
                ON g.date = a.date 
                AND g.country = a.country
                AND a.asn_name = '{asn_filter}'
            GROUP BY g.date, g.country
            ORDER BY g.date, attacks DESC
        """
    else:
        # Top 20 countries with zero-filling
        query = f"""
            WITH top_countries AS (
                SELECT country
                FROM daily_country_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                GROUP BY country
                ORDER BY SUM(attacks) DESC
                LIMIT 10
            ),
            date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            ),
            complete_grid AS (
                SELECT d.date, t.country
                FROM date_range d
                CROSS JOIN top_countries t
            )
            SELECT 
                g.date::VARCHAR as date,
                g.country,
                COALESCE(d.attacks, 0) as attacks
            FROM complete_grid g
            LEFT JOIN daily_country_attacks d 
                ON g.date = d.date 
                AND g.country = d.country
            ORDER BY g.date, attacks DESC
        """
    
    result = conn.execute(query).fetchall()
    conn.close()
    
    data = [{'date': row[0], 'country': row[1], 'attacks': row[2]} for row in result]
    return jsonify(data)


# ============================================================================
# 2. Volatile Countries - WITH ZERO-FILLING
# ============================================================================
# ============================================================================
# UPDATED /api/unusual_countries endpoint - ADD IP FILTER
# Replace in api_summary_only.py
# ============================================================================

@app.route('/api/unusual_countries', methods=['GET'])
def get_unusual_countries():
    """Chart 3: Most Volatile Countries - with zero-filling and IP filter"""
    start, end = parse_date_params()
    country_filter = request.args.get('country')
    asn_filter = request.args.get('asn')
    ip_filter = request.args.get('ip')  # ← NEW
    
    conn = get_db()
    
    if ip_filter:
        # Filter by IP - show volatility of this IP's country
        query = f"""
            WITH ip_country AS (
                SELECT DISTINCT country
                FROM daily_ip_attacks
                WHERE IP = '{ip_filter}'
                LIMIT 1
            ),
            date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            )
            SELECT 
                d.date::VARCHAR as date,
                COALESCE(i.country, (SELECT country FROM ip_country)) as country,
                COALESCE(i.attacks, 0) as attacks,
                COALESCE(
                    CASE 
                        WHEN LAG(i.attacks) OVER (ORDER BY d.date) > 0 
                        THEN ROUND(((COALESCE(i.attacks, 0) - LAG(i.attacks) OVER (ORDER BY d.date)) * 100.0 
                             / LAG(i.attacks) OVER (ORDER BY d.date)), 2)
                        ELSE 0
                    END, 0
                ) as pct_change
            FROM date_range d
            CROSS JOIN ip_country
            LEFT JOIN daily_ip_attacks i
                ON d.date = i.date
                AND i.IP = '{ip_filter}'
            ORDER BY d.date
        """
    elif country_filter:
        # Single country - just return its data with zero-filling
        query = f"""
            WITH date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            )
            SELECT 
                d.date::VARCHAR as date,
                '{country_filter}' as country,
                COALESCE(c.attacks, 0) as attacks,
                COALESCE(
                    CASE 
                        WHEN LAG(c.attacks) OVER (ORDER BY d.date) > 0 
                        THEN ROUND(((COALESCE(c.attacks, 0) - LAG(c.attacks) OVER (ORDER BY d.date)) * 100.0 
                             / LAG(c.attacks) OVER (ORDER BY d.date)), 2)
                        ELSE 0
                    END, 0
                ) as pct_change
            FROM date_range d
            LEFT JOIN daily_country_attacks c 
                ON d.date = c.date 
                AND c.country = '{country_filter}'
            ORDER BY d.date
        """
    elif asn_filter:
        # Filter by ASN - show volatile countries for this ASN
        query = f"""
            WITH asn_daily_data AS (
                SELECT 
                    country,
                    date,
                    SUM(attacks) as attacks,
                    LAG(SUM(attacks)) OVER (PARTITION BY country ORDER BY date) as prev_attacks
                FROM daily_asn_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND asn_name = '{asn_filter}'
                GROUP BY country, date
            ),
            pct_changes AS (
                SELECT 
                    country,
                    date,
                    attacks,
                    prev_attacks,
                    CASE 
                        WHEN prev_attacks > 0 THEN ((attacks - prev_attacks) * 100.0 / prev_attacks)
                        ELSE 0 
                    END as pct_change
                FROM asn_daily_data
                WHERE prev_attacks IS NOT NULL
            ),
            volatile_countries AS (
                SELECT 
                    country,
                    MAX(ABS(pct_change)) as max_pct_change
                FROM pct_changes
                GROUP BY country
                ORDER BY max_pct_change DESC
                LIMIT 10
            ),
            date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            ),
            complete_grid AS (
                SELECT d.date, v.country
                FROM date_range d
                CROSS JOIN volatile_countries v
            )
            SELECT 
                g.date::VARCHAR as date,
                g.country,
                COALESCE(SUM(a.attacks), 0) as attacks,
                COALESCE(
                    CASE 
                        WHEN LAG(SUM(a.attacks)) OVER (PARTITION BY g.country ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(SUM(a.attacks), 0) - LAG(SUM(a.attacks)) OVER (PARTITION BY g.country ORDER BY g.date)) * 100.0 
                             / LAG(SUM(a.attacks)) OVER (PARTITION BY g.country ORDER BY g.date)), 2)
                        ELSE 0
                    END, 0
                ) as pct_change
            FROM complete_grid g
            LEFT JOIN daily_asn_attacks a
                ON g.date = a.date 
                AND g.country = a.country
                AND a.asn_name = '{asn_filter}'
            GROUP BY g.date, g.country
            ORDER BY g.date, attacks DESC
        """
    else:
        # Top 20 volatile countries (existing logic)
        query = f"""
            WITH daily_data AS (
                SELECT 
                    country,
                    date,
                    attacks,
                    LAG(attacks) OVER (PARTITION BY country ORDER BY date) as prev_attacks
                FROM daily_country_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND country != 'Unknown'
                ORDER BY country, date
            ),
            pct_changes AS (
                SELECT 
                    country,
                    date,
                    attacks,
                    prev_attacks,
                    CASE 
                        WHEN prev_attacks > 0 THEN ((attacks - prev_attacks) * 100.0 / prev_attacks)
                        ELSE 0 
                    END as pct_change
                FROM daily_data
                WHERE prev_attacks IS NOT NULL
            ),
            volatile_countries AS (
                SELECT 
                    country,
                    MAX(ABS(pct_change)) as max_pct_change
                FROM pct_changes
                GROUP BY country
                ORDER BY max_pct_change DESC
                LIMIT 10
            ),
            date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            ),
            complete_grid AS (
                SELECT d.date, v.country
                FROM date_range d
                CROSS JOIN volatile_countries v
            )
            SELECT 
                g.date::VARCHAR as date,
                g.country,
                COALESCE(d.attacks, 0) as attacks,
                COALESCE(
                    CASE 
                        WHEN LAG(d.attacks) OVER (PARTITION BY g.country ORDER BY g.date) > 0 
                        THEN ROUND(((COALESCE(d.attacks, 0) - LAG(d.attacks) OVER (PARTITION BY g.country ORDER BY g.date)) * 100.0 
                             / LAG(d.attacks) OVER (PARTITION BY g.country ORDER BY g.date)), 2)
                        ELSE 0
                    END, 0
                ) as pct_change
            FROM complete_grid g
            LEFT JOIN daily_country_attacks d 
                ON g.date = d.date 
                AND g.country = d.country
            ORDER BY g.date, attacks DESC
        """
    
    result = conn.execute(query).fetchall()
    conn.close()
    
    data = [{'date': row[0], 'country': row[1], 'attacks': row[2], 'pct_change': row[3]} for row in result]
    return jsonify(data)


# ============================================================================
# REPLACE the /api/ip_attacks endpoint in api_summary_only.py with this:
# ============================================================================

@app.route('/api/ip_attacks', methods=['GET'])
def get_ip_attacks():
    """Chart 4: Top 20 IPs - with zero-filling and IP filter"""
    start, end = parse_date_params()
    country_filter = request.args.get('country')
    asn_filter = request.args.get('asn')
    ip_filter = request.args.get('ip')  # ← NEW: Check for IP filter
    
    conn = get_db()
    
    if ip_filter:
        # Single IP selected - show only this IP with zero-filling
        query = f"""
            WITH date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            )
            SELECT 
                d.date::VARCHAR as date,
                '{ip_filter}' as IP,
                COALESCE(MAX(i.country), 'Unknown') as country,
                COALESCE(SUM(i.attacks), 0) as attacks
            FROM date_range d
            LEFT JOIN daily_ip_attacks i 
                ON d.date = i.date 
                AND i.IP = '{ip_filter}'
            GROUP BY d.date
            ORDER BY d.date
        """
    else:
        # Build WHERE conditions for finding top IPs
        where_conditions = [f"date BETWEEN '{start}' AND '{end}'"]
        if country_filter:
            where_conditions.append(f"country = '{country_filter}'")
        if asn_filter:
            where_conditions.append(f"asn_name = '{asn_filter}'")
        
        where_clause = " AND ".join(where_conditions)
        
        # Build JOIN conditions for the LEFT JOIN (zero-filling)
        join_conditions = ["g.date = d.date", "g.IP = d.IP", "g.country = d.country"]
        if asn_filter:
            join_conditions.append(f"d.asn_name = '{asn_filter}'")
        
        join_clause = " AND ".join(join_conditions)
        
        query = f"""
            WITH top_ips AS (
                SELECT IP, country
                FROM daily_ip_attacks
                WHERE {where_clause}
                GROUP BY IP, country
                ORDER BY SUM(attacks) DESC
                LIMIT 10
            ),
            date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            ),
            complete_grid AS (
                SELECT d.date, t.IP, t.country
                FROM date_range d
                CROSS JOIN top_ips t
            )
            SELECT 
                g.date::VARCHAR as date,
                g.IP,
                g.country,
                COALESCE(SUM(d.attacks), 0) as attacks
            FROM complete_grid g
            LEFT JOIN daily_ip_attacks d 
                ON {join_clause}
            GROUP BY g.date, g.IP, g.country
            ORDER BY g.date, attacks DESC
        """
    
    result = conn.execute(query).fetchall()
    conn.close()
    
    data = [{'date': row[0], 'IP': row[1], 'country': row[2], 'attacks': row[3]} for row in result]
    return jsonify(data)


# ============================================================================
# 4. Username Attacks - FIXED WITH ASN FILTER
# ============================================================================
@app.route('/api/username_attacks', methods=['GET'])
def get_username_attacks():
    """Chart 5: Top 10 usernames - with zero-filling and IP filter"""
    start, end = parse_date_params()
    country_filter = request.args.get('country')
    asn_filter = request.args.get('asn')
    ip_filter = request.args.get('ip')  # ← NEW
    
    conn = get_db()
    
    if ip_filter:
        # Filter by IP - get top 10 usernames from that IP
        # Uses the NEW daily_ip_username_attacks table
        query = f"""
            WITH top_usernames AS (
                SELECT username
                FROM daily_ip_username_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND IP = '{ip_filter}'
                GROUP BY username
                ORDER BY SUM(attacks) DESC
                LIMIT 10
            ),
            date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            ),
            complete_grid AS (
                SELECT d.date, t.username
                FROM date_range d
                CROSS JOIN top_usernames t
            )
            SELECT 
                g.date::VARCHAR as date,
                g.username,
                'Single IP' as country,
                COALESCE(SUM(d.attacks), 0) as attacks
            FROM complete_grid g
            LEFT JOIN daily_ip_username_attacks d 
                ON g.date = d.date 
                AND g.username = d.username
                AND d.IP = '{ip_filter}'
            GROUP BY g.date, g.username
            ORDER BY g.date, attacks DESC
        """
    elif asn_filter:
        # Filter by ASN - use the OLD daily_username_attacks table
        query = f"""
            WITH top_usernames AS (
                SELECT username
                FROM daily_username_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND asn_name = '{asn_filter}'
                GROUP BY username
                ORDER BY SUM(attacks) DESC
                LIMIT 10
            ),
            date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            ),
            complete_grid AS (
                SELECT d.date, t.username
                FROM date_range d
                CROSS JOIN top_usernames t
            )
            SELECT 
                g.date::VARCHAR as date,
                g.username,
                'Mixed' as country,
                COALESCE(SUM(d.attacks), 0) as attacks
            FROM complete_grid g
            LEFT JOIN daily_username_attacks d 
                ON g.date = d.date 
                AND g.username = d.username
                AND d.asn_name = '{asn_filter}'
            GROUP BY g.date, g.username
            ORDER BY g.date, attacks DESC
        """
    elif country_filter:
        # Filter by country - use the OLD daily_username_attacks table
        query = f"""
            WITH top_usernames AS (
                SELECT username
                FROM daily_username_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND country = '{country_filter}'
                GROUP BY username
                ORDER BY SUM(attacks) DESC
                LIMIT 10
            ),
            date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            ),
            complete_grid AS (
                SELECT d.date, t.username
                FROM date_range d
                CROSS JOIN top_usernames t
            )
            SELECT 
                g.date::VARCHAR as date,
                g.username,
                '{country_filter}' as country,
                COALESCE(SUM(d.attacks), 0) as attacks
            FROM complete_grid g
            LEFT JOIN daily_username_attacks d 
                ON g.date = d.date 
                AND g.username = d.username
                AND d.country = '{country_filter}'
            GROUP BY g.date, g.username
            ORDER BY g.date, attacks DESC
        """
    else:
        # No filter - use the OLD daily_username_attacks table
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
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            ),
            complete_grid AS (
                SELECT d.date, t.username
                FROM date_range d
                CROSS JOIN top_usernames t
            )
            SELECT 
                g.date::VARCHAR as date,
                g.username,
                'Mixed' as country,
                COALESCE(SUM(d.attacks), 0) as attacks
            FROM complete_grid g
            LEFT JOIN daily_username_attacks d 
                ON g.date = d.date 
                AND g.username = d.username
            GROUP BY g.date, g.username
            ORDER BY g.date, attacks DESC
        """
    
    result = conn.execute(query).fetchall()
    conn.close()
    
    data = [{'date': row[0], 'username': row[1], 'country': row[2], 'attacks': row[3]} for row in result]
    return jsonify(data)


# ============================================================================
# 5. ASN Attacks - WITH ZERO-FILLING
# ============================================================================
# ============================================================================
# UPDATED /api/asn_attacks endpoint - ADD IP FILTER
# Replace in api_summary_only.py
# ============================================================================

@app.route('/api/asn_attacks', methods=['GET'])
def get_asn_attacks():
    """Chart 6: Top 20 ASNs - with zero-filling and IP filter"""
    start, end = parse_date_params()
    country_filter = request.args.get('country')
    asn_filter = request.args.get('asn')
    ip_filter = request.args.get('ip')  # ← NEW
    
    conn = get_db()
    
    if ip_filter:
        # Filter by IP - show which ASN this IP belongs to
        query = f"""
            WITH date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            ),
            ip_asn AS (
                SELECT DISTINCT asn_name, country
                FROM daily_ip_attacks
                WHERE IP = '{ip_filter}'
                LIMIT 1
            )
            SELECT 
                d.date::VARCHAR as date,
                COALESCE(i.asn_name, (SELECT asn_name FROM ip_asn)) as asn_name,
                COALESCE(i.country, (SELECT country FROM ip_asn)) as country,
                COALESCE(i.attacks, 0) as attacks
            FROM date_range d
            CROSS JOIN ip_asn
            LEFT JOIN daily_ip_attacks i
                ON d.date = i.date
                AND i.IP = '{ip_filter}'
            ORDER BY d.date
        """
    elif asn_filter:
        # Single ASN - show only this ASN with zero-filling
        query = f"""
            WITH date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            )
            SELECT 
                d.date::VARCHAR as date,
                '{asn_filter}' as asn_name,
                COALESCE(MAX(a.country), 'Mixed') as country,
                COALESCE(SUM(a.attacks), 0) as attacks
            FROM date_range d
            LEFT JOIN daily_asn_attacks a 
                ON d.date = a.date 
                AND a.asn_name = '{asn_filter}'
            GROUP BY d.date
            ORDER BY d.date
        """
    elif country_filter:
        # Filter by country, get top 20 ASNs from that country
        query = f"""
            WITH top_asns AS (
                SELECT asn_name
                FROM daily_asn_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND country = '{country_filter}'
                GROUP BY asn_name
                ORDER BY SUM(attacks) DESC
                LIMIT 10
            ),
            date_range AS (
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            ),
            complete_grid AS (
                SELECT d.date, t.asn_name
                FROM date_range d
                CROSS JOIN top_asns t
            )
            SELECT 
                g.date::VARCHAR as date,
                g.asn_name,
                '{country_filter}' as country,
                COALESCE(SUM(d.attacks), 0) as attacks
            FROM complete_grid g
            LEFT JOIN daily_asn_attacks d 
                ON g.date = d.date 
                AND g.asn_name = d.asn_name
                AND d.country = '{country_filter}'
            GROUP BY g.date, g.asn_name
            ORDER BY g.date, attacks DESC
        """
    else:
        # No filter, aggregate across all countries
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
                SELECT UNNEST(generate_series(
                    DATE '{start}',
                    DATE '{end}',
                    INTERVAL 1 DAY
                ))::DATE as date
            ),
            complete_grid AS (
                SELECT d.date, t.asn_name
                FROM date_range d
                CROSS JOIN top_asns t
            )
            SELECT 
                g.date::VARCHAR as date,
                g.asn_name,
                'Mixed' as country,
                COALESCE(SUM(d.attacks), 0) as attacks
            FROM complete_grid g
            LEFT JOIN daily_asn_attacks d 
                ON g.date = d.date 
                AND g.asn_name = d.asn_name
            GROUP BY g.date, g.asn_name
            ORDER BY g.date, attacks DESC
        """
    
    result = conn.execute(query).fetchall()
    conn.close()
    
    data = [{'date': row[0], 'asn_name': row[1], 'country': row[2], 'attacks': row[3]} for row in result]
    return jsonify(data)




@app.route('/api/date_range', methods=['GET'])
def get_date_range():
    """Get available date range"""
    conn = get_db()
    result = conn.execute("""
        SELECT 
            MIN(date)::VARCHAR as min_date,
            MAX(date)::VARCHAR as max_date
        FROM daily_stats
    """).fetchone()
    conn.close()
    
    return jsonify({
        'min_date': result[0] if result else None,
        'max_date': result[1] if result else None
    })


@app.route('/')
def index():
    """API documentation"""
    return jsonify({
        'name': 'Attack Data Visualization API',
        'status': 'running',
        'endpoints': {
            '/api/total_attacks': 'Total attacks over time',
            '/api/country_attacks': 'Top 10 countries',
            '/api/unusual_countries': 'Volatile countries',
            '/api/ip_attacks': 'Top 10 IPs',
            '/api/username_attacks': 'Top 10 usernames',
            '/api/asn_attacks': 'Top 10 ASNs',
            '/api/date_range': 'Available dates'
        },
        'note': 'Uses only summary tables - fast queries!'
    })

if __name__ == '__main__':
    print("="*70)
    print("Attack Data Visualization API")
    print("Using ONLY summary tables (no raw data queries)")
    print("="*70)
    print(f"\n📊 Database: {DB_PATH}")
    print(f"🌐 Server: http://localhost:5000")
    print(f"📝 API Docs: http://localhost:5000")
    print("\n✅ This version avoids file limit issues!")
    print("="*70)
    
    app.run(debug=True, host='0.0.0.0', port=5000)