#!/usr/bin/env python3
"""
Find Top 10 Most Volatile Countries
Based on maximum day-to-day percentage change in attacks
"""

import duckdb

DB_PATH = './attack_data.db'

def main():
    print("="*70)
    print("Top 10 Most Volatile Countries")
    print("Based on Maximum Day-to-Day Percentage Change")
    print("="*70)
    
    conn = duckdb.connect(DB_PATH, read_only=True)
    
    # Calculate day-to-day percentage changes for each country
    query = """
    WITH daily_data AS (
        SELECT 
            country,
            date,
            attacks,
            LAG(attacks) OVER (PARTITION BY country ORDER BY date) as prev_attacks
        FROM daily_country_attacks
        WHERE country != 'Unknown'
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
    max_changes AS (
        SELECT 
            country,
            MAX(ABS(pct_change)) as max_pct_change,
            -- Also get the date and details of the max change
            FIRST(date ORDER BY ABS(pct_change) DESC) as max_change_date,
            FIRST(attacks ORDER BY ABS(pct_change) DESC) as attacks_on_max,
            FIRST(prev_attacks ORDER BY ABS(pct_change) DESC) as prev_attacks_on_max,
            FIRST(pct_change ORDER BY ABS(pct_change) DESC) as actual_pct_change
        FROM pct_changes
        GROUP BY country
    )
    SELECT 
        country,
        max_pct_change,
        max_change_date,
        prev_attacks_on_max,
        attacks_on_max,
        actual_pct_change
    FROM max_changes
    ORDER BY max_pct_change DESC
    LIMIT 10
    """
    
    results = conn.execute(query).fetchall()
    
    print("\nTop 10 Most Volatile Countries:\n")
    print(f"{'Rank':<5} {'Country':<30} {'Max % Change':>15} {'Date':>12} {'From → To Attacks'}")
    print("="*90)
    
    for i, (country, max_pct, date, prev_attacks, attacks, actual_pct) in enumerate(results, 1):
        direction = "↑" if actual_pct > 0 else "↓"
        print(f"{i:<5} {country[:28]:<30} {direction}{max_pct:>12,.1f}% {str(date):>12} {prev_attacks:>8,} → {attacks:>8,}")
    
    # Also show their total attacks for context
    print("\n" + "="*70)
    print("Total Attacks Context:\n")
    
    country_list = "', '".join([r[0] for r in results])
    totals = conn.execute(f"""
        SELECT country, SUM(attacks) as total_attacks
        FROM daily_country_attacks
        WHERE country IN ('{country_list}')
        GROUP BY country
        ORDER BY total_attacks DESC
    """).fetchall()
    
    for country, total_attacks in totals:
        print(f"  {country[:40]:<40} {total_attacks:>15,}")
    
    conn.close()
    
    print("\n" + "="*70)
    print("✅ These are the countries with the biggest day-to-day swings!")
    print("="*70)


if __name__ == "__main__":
    main()
