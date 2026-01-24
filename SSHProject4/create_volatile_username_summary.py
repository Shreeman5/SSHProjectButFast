#!/usr/bin/env python3
"""
Create Volatile Username Summary Table
Pre-computes maximum day-to-day percentage changes for fast querying
"""
import duckdb
import configparser

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')
DB_PATH = config['paths']['duckdb_path']

def main():
    print("="*70)
    print("Creating Volatile Username Summary Table")
    print("="*70)
    
    conn = duckdb.connect(DB_PATH)
    
    # Drop existing table if it exists
    print("\n1. Dropping existing table (if exists)...")
    conn.execute("DROP TABLE IF EXISTS volatile_username_summary")
    
    # Create the volatile summary table
    print("2. Creating volatile_username_summary table...")
    print("   (This may take a while - calculating volatility for all usernames...)")
    
    conn.execute("""
        CREATE TABLE volatile_username_summary AS
        WITH daily_data AS (
            SELECT 
                username,
                date,
                SUM(attacks) as attacks,
                LAG(SUM(attacks)) OVER (PARTITION BY username ORDER BY date) as prev_attacks
            FROM daily_username_attacks
            GROUP BY username, date
        ),
        pct_changes AS (
            SELECT 
                username,
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
        max_changes AS (
            SELECT 
                username,
                MAX(ABS(pct_change)) as max_volatility,
                FIRST(date ORDER BY ABS(pct_change) DESC) as max_change_date,
                FIRST(attacks ORDER BY ABS(pct_change) DESC) as attacks_on_max,
                FIRST(prev_attacks ORDER BY ABS(pct_change) DESC) as prev_attacks_on_max
            FROM pct_changes
            GROUP BY username
        )
        SELECT * FROM max_changes
        ORDER BY max_volatility DESC
    """)
    
    # Get count
    count = conn.execute("SELECT COUNT(*) FROM volatile_username_summary").fetchone()[0]
    print(f"3. Created table with {count:,} usernames")
    
    # Show top 10
    print("\n4. Top 10 Most Volatile Usernames:")
    print(f"{'Rank':<5} {'Username':<30} {'Max Volatility':>15}")
    print("="*55)
    
    top10 = conn.execute("""
        SELECT username, max_volatility 
        FROM volatile_username_summary 
        ORDER BY max_volatility DESC 
        LIMIT 10
    """).fetchall()
    
    for i, (username, volatility) in enumerate(top10, 1):
        print(f"{i:<5} {username[:28]:<30} {volatility:>14.1f}%")
    
    conn.close()
    
    print("\n" + "="*70)
    print("✅ Volatile username summary table created successfully!")
    print("="*70)

if __name__ == "__main__":
    main()
