#!/usr/bin/env python3
"""
Example Queries - DuckDB
Demonstrates fast analytical queries on 213M rows
"""

import duckdb
from pathlib import Path
import configparser
import time

def run_example_queries(duckdb_path):
    """Run example queries to demonstrate performance"""
    
    if not Path(duckdb_path).exists():
        print(f"❌ Database not found: {duckdb_path}")
        print("Please run 02_setup_duckdb.py first")
        return
    
    print("="*70)
    print("DuckDB Example Queries")
    print("Demonstrating sub-second queries on 213M rows")
    print("="*70)
    
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    
    queries = {
        "📊 Total Attacks": """
            SELECT COUNT(*) as total_attacks FROM attacks
        """,
        
        "🌍 Attacks by Continent": """
            SELECT 
                continent,
                COUNT(*) as attacks,
                COUNT(DISTINCT IP) as unique_ips
            FROM attacks
            WHERE continent IS NOT NULL
            GROUP BY continent
            ORDER BY attacks DESC
        """,
        
        "🗺️ Top 10 Countries": """
            SELECT 
                country,
                total_attacks,
                unique_ips,
                unique_usernames
            FROM country_stats
            ORDER BY total_attacks DESC
            LIMIT 10
        """,
        
        "📅 Attacks Per Day (Last 30 days)": """
            SELECT 
                date,
                total_attacks,
                unique_ips
            FROM daily_stats
            ORDER BY date DESC
            LIMIT 30
        """,
        
        "🔝 Top 20 Attacking IPs": """
            SELECT 
                IP,
                COALESCE(country, 'Unknown') as country,
                COALESCE(asn_name, 'Unknown') as asn_name,
                attack_count
            FROM top_ips
            ORDER BY attack_count DESC
            LIMIT 20
        """,
        
        "👤 Most Common Usernames": """
            SELECT 
                Username,
                attempt_count,
                unique_ips,
                unique_countries
            FROM username_stats
            ORDER BY attempt_count DESC
            LIMIT 20
        """,
        
        "🏢 Top ASN Organizations": """
            SELECT 
                asn_name,
                COUNT(*) as attacks,
                COUNT(DISTINCT IP) as unique_ips
            FROM attacks
            WHERE asn_name IS NOT NULL
            GROUP BY asn_name
            ORDER BY attacks DESC
            LIMIT 15
        """,
        
        "🕐 Hourly Attack Pattern": """
            SELECT 
                hour,
                attack_count,
                unique_ips,
                ROUND(100.0 * attack_count / SUM(attack_count) OVER (), 2) as percentage
            FROM hourly_patterns
            ORDER BY hour
        """,
        
        "🔍 Data Quality Check": """
            SELECT 
                'Total Records' as metric,
                CAST(COUNT(*) AS VARCHAR) as count
            FROM attacks
            UNION ALL
            SELECT 
                'Missing Country Info',
                CAST(COUNT(*) AS VARCHAR)
            FROM attacks 
            WHERE country IS NULL OR country = 'None' OR country = 'Unknown'
            UNION ALL
            SELECT 
                'Missing ASN Info',
                CAST(COUNT(*) AS VARCHAR)
            FROM attacks 
            WHERE asn IS NULL OR asn = 'None' OR asn = 'Unknown'
            UNION ALL
            SELECT 
                'Port Column Sample',
                'Check manually: SELECT DISTINCT Port FROM attacks LIMIT 20'
        """,
        
        "🎯 Attacks on Port 22 vs Others": """
            SELECT 
                CASE 
                    WHEN CAST(Port AS VARCHAR) = '22' THEN 'SSH (Port 22)' 
                    ELSE 'Other Ports'
                END as port_type,
                COUNT(*) as attacks,
                ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as percentage
            FROM attacks
            GROUP BY port_type
        """,
        
        "📈 Attack Trend (Weekly)": """
            SELECT 
                DATE_TRUNC('week', date) as week,
                SUM(total_attacks) as attacks,
                AVG(unique_ips) as avg_daily_ips
            FROM daily_stats
            GROUP BY week
            ORDER BY week DESC
            LIMIT 12
        """
    }
    
    for query_name, query in queries.items():
        print(f"\n{query_name}")
        print("-" * 70)
        
        start = time.time()
        result = conn.execute(query).fetchall()
        elapsed = time.time() - start
        
        print(f"⏱️  Query time: {elapsed:.3f} seconds")
        print(f"📊 Results:\n")
        
        # Print results in a nice format
        for row in result:
            formatted_row = []
            for val in row:
                if isinstance(val, int) and val > 1000:
                    formatted_row.append(f"{val:,}")
                elif isinstance(val, float):
                    formatted_row.append(f"{val:.2f}")
                else:
                    formatted_row.append(str(val))
            print(f"   {' | '.join(formatted_row)}")
    
    conn.close()
    
    print("\n" + "="*70)
    print("✅ All queries completed!")
    print("="*70)
    print("\n💡 Notice how fast these queries run on 213M rows!")
    print("   Most queries complete in under 1 second")


def main():
    """Main execution"""
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    try:
        duckdb_path = config['paths']['duckdb_path']
    except KeyError:
        print("❌ Config file missing duckdb_path")
        return
    
    run_example_queries(duckdb_path)


if __name__ == "__main__":
    main()
