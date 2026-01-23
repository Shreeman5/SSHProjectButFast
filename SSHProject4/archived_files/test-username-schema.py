#!/usr/bin/env python3
"""
Check schemas for username and IP tables
"""

import duckdb
import configparser

# Load configuration
config = configparser.ConfigParser()
config.read('config.ini')
DB_PATH = config['paths']['duckdb_path']

def main():
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    
    print("="*70)
    print("TABLE SCHEMA CHECK")
    print("="*70)
    
    # Check username table
    print("\n1. daily_username_attacks TABLE:")
    print("-" * 70)
    schema = conn.execute("DESCRIBE daily_username_attacks").fetchall()
    print("Columns:")
    for col_name, col_type, *_ in schema:
        print(f"  - {col_name:20s} ({col_type})")
    
    print("\nSample data (first 2 rows):")
    sample = conn.execute("SELECT * FROM daily_username_attacks LIMIT 2").fetchall()
    for row in sample:
        print(f"  {row}")
    
    # Check IP table
    print("\n" + "="*70)
    print("2. daily_ip_attacks TABLE:")
    print("-" * 70)
    schema = conn.execute("DESCRIBE daily_ip_attacks").fetchall()
    print("Columns:")
    for col_name, col_type, *_ in schema:
        print(f"  - {col_name:20s} ({col_type})")
    
    print("\nSample data (first 2 rows):")
    sample = conn.execute("SELECT * FROM daily_ip_attacks LIMIT 2").fetchall()
    for row in sample:
        print(f"  {row}")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY - What filtering is possible:")
    print("="*70)
    
    username_cols = [row[0] for row in conn.execute("DESCRIBE daily_username_attacks").fetchall()]
    ip_cols = [row[0] for row in conn.execute("DESCRIBE daily_ip_attacks").fetchall()]
    
    print("\n✓ Username table has these filters:")
    if 'country' in username_cols:
        print("  ✓ country (can filter by country)")
    if 'asn_name' in username_cols:
        print("  ✓ asn_name (can filter by ASN)")
    if 'IP' in username_cols:
        print("  ✓ IP (can filter by IP)")
    else:
        print("  ✗ IP (CANNOT filter usernames by IP)")
    
    print("\n✓ IP table has these filters:")
    if 'country' in ip_cols:
        print("  ✓ country (can show country chart)")
    if 'asn_name' in ip_cols:
        print("  ✓ asn_name (can show ASN chart)")
    
    conn.close()
    
    print("\n" + "="*70)

if __name__ == "__main__":
    main()