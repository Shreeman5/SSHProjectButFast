#!/usr/bin/env python3
"""
Preview Parquet File Contents
Shows all columns with example data
"""

import pandas as pd
import sys
from pathlib import Path

def preview_parquet(parquet_file):
    """Display comprehensive preview of parquet file"""
    
    if not Path(parquet_file).exists():
        print(f"❌ File not found: {parquet_file}")
        return
    
    # Read the parquet file
    df = pd.read_parquet(parquet_file)
    
    print("="*80)
    print("PARQUET FILE PREVIEW - All 20 Columns")
    print("="*80)
    print(f"\nFile: {parquet_file}")
    print(f"Total rows: {len(df):,}")
    print(f"Total columns: {len(df.columns)}")
    
    print("\n" + "="*80)
    print("COLUMN LIST WITH DATA TYPES & EXAMPLES")
    print("="*80)
    for i, col in enumerate(df.columns, 1):
        example_val = df[col].iloc[0]
        if isinstance(example_val, str) and len(example_val) > 40:
            example_val = example_val[:40] + "..."
        print(f"{i:2d}. {col:20s} | {str(df[col].dtype):15s} | Example: {example_val}")
    
    print("\n" + "="*80)
    print("SAMPLE DATA BY CATEGORY (First 3 rows)")
    print("="*80)
    
    print("\n📅 DATE/TIME COLUMNS:")
    print(df[['datetime', 'year', 'month']].head(3).to_string(index=False))
    
    print("\n🌐 IP & BASIC INFO:")
    print(df[['IP', 'Time', 'Node', 'Port']].head(3).to_string(index=False))
    
    print("\n🗺️ GEO ENRICHMENT (from JSON):")
    print(df[['IP', 'continent', 'country', 'latitude', 'longitude']].head(3).to_string(index=False))
    
    print("\n🏢 ASN/ORGANIZATION INFO (from JSON):")
    print(df[['IP', 'asn', 'asn_name', 'asn_type']].head(3).to_string(index=False))
    
    print("\n🔐 ATTACK DETAILS:")
    print(df[['Username', 'PID', 'Tag']].head(3).to_string(index=False))
    
    print("\n📝 FULL MESSAGE EXAMPLES:")
    for i in range(min(3, len(df))):
        msg = str(df['Message'].iloc[i])
        print(f"\n  Row {i+1}:")
        print(f"    {msg[:120]}")
        if len(msg) > 120:
            print(f"    {msg[120:240]}...")
    
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print(f"Unique IPs: {df['IP'].nunique():,}")
    print(f"Unique Countries: {df['country'].nunique()}")
    print(f"Top 5 Countries: {df['country'].value_counts().head(5).to_dict()}")
    print(f"Unique Usernames: {df['Username'].nunique()}")
    print(f"Top 5 Usernames: {df['Username'].value_counts().head(5).to_dict()}")
    print(f"Unique Nodes: {df['Node'].nunique()}")
    print(f"Date Range: {df['datetime'].min()} to {df['datetime'].max()}")
    
    print("\n" + "="*80)
    print("✅ Preview Complete")
    print("="*80)

if __name__ == "__main__":
    # Default to test file
    parquet_file = "./parquet_output/test_output/test_sample.parquet"
    
    if len(sys.argv) > 1:
        parquet_file = sys.argv[1]
    
    preview_parquet(parquet_file)
