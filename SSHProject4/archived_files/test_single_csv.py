#!/usr/bin/env python3
"""
Test Conversion - Single CSV File
Debug why only first chunk gets enriched
"""

import pandas as pd
import json
from pathlib import Path

# Configuration
CSV_FILE = 'csv_files/clem/20230105.csv'  # Test with one file
JSON_FILE = 'ipinfo.json'
OUTPUT_DIR = Path('./test_parquet_output')
CHUNK_SIZE = 100000

print("="*70)
print("Test Conversion - Single CSV")
print("="*70)

# Load IP data
print(f"\n📂 Loading IP lookup: {JSON_FILE}")
with open(JSON_FILE) as f:
    ip_data = json.load(f)
print(f"✅ Loaded {len(ip_data):,} IPs")

# Enrichment function
def enrich_row_with_ip_data(ip):
    """Enrich IP with geolocation data"""
    if ip not in ip_data:
        return {
            'continent': None,
            'country_code': None,
            'country': None,
            'latitude': None,
            'longitude': None,
            'asn': None,
            'asn_name': None,
            'asn_domain': None,
            'asn_type': None
        }
    
    ip_info = ip_data[ip]
    asn_info = ip_info.get('asn', {})
    
    return {
        'continent': ip_info.get('cntn', None),
        'country_code': ip_info.get('cc', None),
        'country': ip_info.get('cn', None),
        'latitude': ip_info.get('lat'),
        'longitude': ip_info.get('lng'),
        'asn': asn_info.get('asn', None),
        'asn_name': asn_info.get('name', None),
        'asn_domain': asn_info.get('domain', None),
        'asn_type': asn_info.get('type', None)
    }

# Create output directory
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Process CSV
print(f"\n📄 Processing: {CSV_FILE}")
print(f"📦 Output: {OUTPUT_DIR}")

chunk_num = 0
files_written = []

for chunk in pd.read_csv(CSV_FILE, chunksize=CHUNK_SIZE, low_memory=False):
    chunk_num += 1
    
    print(f"\n{'='*70}")
    print(f"Chunk {chunk_num}: {len(chunk)} rows")
    print(f"{'='*70}")
    
    # Convert datetime
    chunk['datetime'] = pd.to_datetime(chunk['Date'].astype(str), format='%Y%m%d', errors='coerce')
    chunk['year'] = chunk['datetime'].dt.year
    chunk['month'] = chunk['datetime'].dt.month
    
    # Fix types
    chunk['Time'] = pd.to_numeric(chunk['Time'], errors='coerce').fillna(0).astype('int64')
    chunk['Port'] = pd.to_numeric(chunk['Port'], errors='coerce').fillna(0).astype('int64')
    
    for col in ['IP', 'Node', 'PID', 'Username', 'Tag', 'Message']:
        chunk[col] = chunk[col].astype(str)
    
    # ENRICH
    print(f"🔄 Enriching chunk {chunk_num}...")
    ip_enrichment = chunk['IP'].apply(enrich_row_with_ip_data)
    enrichment_df = pd.DataFrame(ip_enrichment.tolist(), index=chunk.index)
    
    # Check enrichment
    non_null_country = enrichment_df['country'].notna().sum()
    print(f"✅ Enrichment result: {non_null_country}/{len(chunk)} rows have country")
    
    # Show sample
    print(f"\n📊 Sample enrichment (first 3 rows):")
    for i in range(min(3, len(chunk))):
        ip = chunk.iloc[i]['IP']
        country = enrichment_df.iloc[i]['country']
        print(f"   IP: {ip} -> Country: {country or 'NULL'}")
    
    # Combine
    enriched_chunk = pd.concat([chunk, enrichment_df], axis=1)
    
    # Drop Date
    enriched_chunk = enriched_chunk.drop(columns=['Date'])
    
    # Reorder columns
    column_order = [
        'datetime', 'year', 'month', 'IP', 'Time',
        'continent', 'country_code', 'country', 'latitude', 'longitude',
        'asn', 'asn_name', 'asn_domain', 'asn_type',
        'Node', 'Port', 'PID', 'Username', 'Tag', 'Message'
    ]
    enriched_chunk = enriched_chunk[column_order]
    
    # Write to parquet
    output_file = OUTPUT_DIR / f"chunk_{chunk_num}.parquet"
    enriched_chunk.to_parquet(output_file, engine='pyarrow', compression='snappy', index=False)
    files_written.append(output_file)
    
    print(f"💾 Written to: {output_file.name}")

print("\n" + "="*70)
print("Conversion Complete!")
print("="*70)
print(f"Chunks processed: {chunk_num}")
print(f"Files written: {len(files_written)}")

# Verify each file
print("\n" + "="*70)
print("Verification - Reading Back Files")
print("="*70)

import duckdb
conn = duckdb.connect(':memory:')

for i, file in enumerate(files_written, 1):
    result = conn.execute(f"""
        SELECT 
            COUNT(*) as total,
            COUNT(country) as with_country,
            COUNT(CASE WHEN country IS NOT NULL THEN 1 END) as non_null
        FROM read_parquet('{file}')
    """).fetchone()
    
    total, with_country, non_null = result
    pct = (non_null / total * 100) if total > 0 else 0
    
    status = "✅" if pct > 90 else "❌"
    print(f"{status} Chunk {i}: {non_null:,}/{total:,} have country ({pct:.1f}%)")

conn.close()

print("\n" + "="*70)
print("✅ Test complete!")
print(f"Check files in: {OUTPUT_DIR}/")
print("="*70)
