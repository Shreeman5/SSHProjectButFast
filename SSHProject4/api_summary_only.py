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


@app.route('/api/country_attacks', methods=['GET'])
def get_country_attacks():
    """Chart 2: Top 10 countries - with date range filtering in top 10 selection"""
    start, end = parse_date_params()
    country_filter = request.args.get('country')
    
    conn = get_db()
    
    if country_filter:
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
    else:
        query = f"""
            WITH top_countries AS (
                SELECT country
                FROM daily_country_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                GROUP BY country
                ORDER BY SUM(attacks) DESC
                LIMIT 10
            )
            SELECT 
                d.date::VARCHAR as date,
                d.country,
                d.attacks
            FROM daily_country_attacks d
            INNER JOIN top_countries t ON d.country = t.country
            WHERE d.date BETWEEN '{start}' AND '{end}'
            ORDER BY d.date, d.attacks DESC
        """
    
    result = conn.execute(query).fetchall()
    conn.close()
    
    data = [{'date': row[0], 'country': row[1], 'attacks': row[2]} for row in result]
    return jsonify(data)


# Replace the get_unusual_countries function in api_summary_only.py with this:
@app.route('/api/unusual_countries', methods=['GET'])
def get_unusual_countries():
    """Chart 3: Most Volatile Countries - REAL DATA with date range filtering"""
    start, end = parse_date_params()
    
    conn = get_db()
    
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
        )
        SELECT 
            d.date::VARCHAR as date,
            d.country,
            d.attacks,
            -- Calculate percentage change from previous day
            CASE 
                WHEN LAG(d.attacks) OVER (PARTITION BY d.country ORDER BY d.date) > 0 
                THEN ROUND(((d.attacks - LAG(d.attacks) OVER (PARTITION BY d.country ORDER BY d.date)) * 100.0 
                     / LAG(d.attacks) OVER (PARTITION BY d.country ORDER BY d.date)), 2)
                ELSE 0
            END as pct_change
        FROM daily_country_attacks d
        INNER JOIN volatile_countries v ON d.country = v.country
        WHERE d.date BETWEEN '{start}' AND '{end}'
        ORDER BY d.date, d.attacks DESC
    """
    
    result = conn.execute(query).fetchall()
    conn.close()
    
    data = [{'date': row[0], 'country': row[1], 'attacks': row[2], 'pct_change': row[3]} for row in result]
    return jsonify(data)


@app.route('/api/ip_attacks', methods=['GET'])
def get_ip_attacks():
    """Chart 4: Top 10 IPs - with date range filtering and zero-filling"""
    start, end = parse_date_params()
    country_filter = request.args.get('country')
    
    conn = get_db()
    
    if country_filter:
        # Filter by country first, then get top 10 from date range
        query = f"""
            WITH top_ips AS (
                SELECT IP, country
                FROM daily_ip_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
                  AND country = '{country_filter}'
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
                ON g.date = d.date 
                AND g.IP = d.IP 
                AND g.country = d.country
            GROUP BY g.date, g.IP, g.country
            ORDER BY g.date, attacks DESC
        """
    else:
        query = f"""
            WITH top_ips AS (
                SELECT IP, country
                FROM daily_ip_attacks
                WHERE date BETWEEN '{start}' AND '{end}'
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
                ON g.date = d.date 
                AND g.IP = d.IP 
                AND g.country = d.country
            GROUP BY g.date, g.IP, g.country
            ORDER BY g.date, attacks DESC
        """
    
    result = conn.execute(query).fetchall()
    conn.close()
    
    data = [{'date': row[0], 'IP': row[1], 'country': row[2], 'attacks': row[3]} for row in result]
    return jsonify(data)


@app.route('/api/username_attacks', methods=['GET'])
def get_username_attacks():
    """Chart 5: Top usernames - with date range filtering in top 10 selection"""
    start, end = parse_date_params()
    country_filter = request.args.get('country')
    
    conn = get_db()
    
    # Note: daily_username_attacks doesn't have country data,
    # so country filter is ignored for now
    
    query = f"""
        WITH top_usernames AS (
            SELECT username
            FROM daily_username_attacks
            WHERE date BETWEEN '{start}' AND '{end}'
            GROUP BY username
            ORDER BY SUM(attacks) DESC
            LIMIT 10
        )
        SELECT 
            d.date::VARCHAR as date,
            d.username,
            'Mixed' as country,
            d.attacks
        FROM daily_username_attacks d
        INNER JOIN top_usernames t ON d.username = t.username
        WHERE d.date BETWEEN '{start}' AND '{end}'
        ORDER BY d.date, d.attacks DESC
    """
    
    result = conn.execute(query).fetchall()
    conn.close()
    
    data = [{'date': row[0], 'username': row[1], 'country': row[2], 'attacks': row[3]} for row in result]
    return jsonify(data)



@app.route('/api/asn_attacks', methods=['GET'])
def get_asn_attacks():
    """Chart 6: Top ASNs - REAL DATA with date range filtering"""
    start, end = parse_date_params()
    country_filter = request.args.get('country')
    
    conn = get_db()
    
    if country_filter:
        # If country filter is active, we can't accurately filter ASNs by country
        # since daily_asn_attacks doesn't have country data
        # For now, just return top 10 overall from date range
        pass
    
    query = f"""
        WITH top_asns AS (
            SELECT asn_name
            FROM daily_asn_attacks
            WHERE date BETWEEN '{start}' AND '{end}'
            GROUP BY asn_name
            ORDER BY SUM(attacks) DESC
            LIMIT 10
        ),
        aggregated AS (
            SELECT 
                d.date,
                d.asn_name,
                SUM(d.attacks) as attacks
            FROM daily_asn_attacks d
            INNER JOIN top_asns t ON d.asn_name = t.asn_name
            WHERE d.date BETWEEN '{start}' AND '{end}'
            GROUP BY d.date, d.asn_name
        )
        SELECT 
            date::VARCHAR as date,
            asn_name,
            'Mixed' as country,
            attacks
        FROM aggregated
        ORDER BY date, attacks DESC
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