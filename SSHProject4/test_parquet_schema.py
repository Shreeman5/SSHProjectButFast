#!/usr/bin/env python3
"""
Test Script: Check Parquet File Schema
See what columns are available, especially for ASN
"""

import duckdb
from pathlib import Path

PARQUET_DIR = Path('./parquet_output')

def main():
    print("="*70)
    print("Testing Parquet File Schema")
    print("="*70)
    
    # Find first parquet file
    all_files = sorted(PARQUET_DIR.glob("year=*/month=*/*.parquet"))
    
    if not all_files:
        print("❌ No parquet files found!")
        return
    
    test_file = all_files[0]
    print(f"\n📂 Testing file: {test_file}")
    
    # Connect to database
    conn = duckdb.connect(':memory:')
    
    # Get schema
    print(f"\n🔍 Columns in parquet file:")
    schema = conn.execute(f"""
        DESCRIBE SELECT * FROM read_parquet('{test_file}')
    """).fetchall()
    
    for col_name, col_type, *_ in schema:
        print(f"   - {col_name:20s} ({col_type})")
    
    # Get sample data
    print(f"\n📊 Sample rows (first 3):")
    sample = conn.execute(f"""
        SELECT * FROM read_parquet('{test_file}')
        LIMIT 3
    """).fetchall()
    
    column_names = [row[0] for row in schema]
    
    for i, row in enumerate(sample, 1):
        print(f"\n   Row {i}:")
        for col_name, value in zip(column_names, row):
            if value is not None:
                print(f"      {col_name:20s}: {value}")
    
    # Check for ASN-related columns
    print(f"\n🔍 ASN-related columns:")
    asn_columns = [col for col in column_names if 'asn' in col.lower()]
    if asn_columns:
        print(f"   Found: {', '.join(asn_columns)}")
        
        # Show sample ASN values
        for asn_col in asn_columns:
            print(f"\n   Sample values from '{asn_col}':")
            asn_samples = conn.execute(f"""
                SELECT DISTINCT {asn_col}
                FROM read_parquet('{test_file}')
                WHERE {asn_col} IS NOT NULL
                LIMIT 5
            """).fetchall()
            for val, in asn_samples:
                print(f"      - {val}")
    else:
        print(f"   ❌ No ASN columns found!")
        print(f"   Available columns: {', '.join(column_names)}")
    
    conn.close()
    
    print(f"\n{'='*70}")
    print("✅ Done!")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
