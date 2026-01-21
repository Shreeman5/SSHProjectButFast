#!/usr/bin/env python3
"""
Verify ASN data exists in Parquet files
Run this in your project directory where parquet_output/ exists
"""

import duckdb
from pathlib import Path

PARQUET_DIR = Path('./parquet_output')

conn = duckdb.connect(':memory:')

print("="*70)
print("ASN Data Verification")
print("="*70)

# Check if directory exists
if not PARQUET_DIR.exists():
    print(f"\n❌ Directory not found: {PARQUET_DIR}")
    print("Run this script from your project directory!")
    exit(1)

# Get sample files
sample_files = list(PARQUET_DIR.glob("year=2022/month=11/*.parquet"))[:3]

if not sample_files:
    print("\n❌ No parquet files found!")
    exit(1)

print(f"\n📂 Checking {len(sample_files)} sample files...")

for pf in sample_files:
    print(f"\n📁 {pf.name}")
    
    result = conn.execute(f"""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN asn IS NOT NULL THEN 1 ELSE 0 END) as has_asn,
            SUM(CASE WHEN asn_name IS NOT NULL THEN 1 ELSE 0 END) as has_asn_name
        FROM read_parquet('{pf}')
    """).fetchone()
    
    print(f"   Rows: {result[0]:,}")
    print(f"   With ASN: {result[1]:,} ({result[1]/result[0]*100:.1f}%)")
    print(f"   With ASN name: {result[2]:,} ({result[2]/result[0]*100:.1f}%)")

# Check Nov 1 for DigitalOcean
print(f"\n{'='*70}")
print("Checking Nov 1, 2022 - DigitalOcean")
print("="*70)

nov1_files = list(PARQUET_DIR.glob("year=2022/month=11/data_2022-11-01*.parquet"))

if nov1_files:
    files_str = "', '".join(str(f) for f in nov1_files)
    
    result = conn.execute(f"""
        SELECT COUNT(*) as attacks
        FROM read_parquet(['{files_str}'])
        WHERE asn_name LIKE '%DigitalOcean%'
    """).fetchone()
    
    print(f"\n✅ DigitalOcean attacks on Nov 1: {result[0]:,}")
    
    # Top 5 ASNs on Nov 1
    print(f"\n📊 Top 5 ASNs on Nov 1, 2022:")
    top = conn.execute(f"""
        SELECT asn_name, COUNT(*) as attacks
        FROM read_parquet(['{files_str}'])
        WHERE asn_name IS NOT NULL
        GROUP BY asn_name
        ORDER BY attacks DESC
        LIMIT 5
    """).fetchall()
    
    for asn_name, attacks in top:
        print(f"   {asn_name}: {attacks:,}")

conn.close()
