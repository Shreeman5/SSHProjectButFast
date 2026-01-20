#!/usr/bin/env python3
"""
Data Validation Script
Tests your setup and shows a preview before full conversion
"""

import json
import pandas as pd
from pathlib import Path
import glob
import sys

def validate_json(json_path):
    """Validate and preview JSON file"""
    print("\n" + "="*70)
    print("1. Validating JSON File")
    print("="*70)
    
    json_path = Path(json_path)
    
    if not json_path.exists():
        print(f"❌ JSON file not found: {json_path}")
        return False
    
    print(f"✅ JSON file exists: {json_path}")
    print(f"   Size: {json_path.stat().st_size / (1024**2):.2f} MB")
    
    # Load and preview
    try:
        with open(json_path, 'r') as f:
            ip_data = json.load(f)
        
        print(f"✅ JSON loaded successfully")
        print(f"   Total IPs: {len(ip_data):,}")
        
        # Show a few examples
        print("\n   Sample entries:")
        for i, (ip, data) in enumerate(list(ip_data.items())[:3]):
            print(f"\n   IP: {ip}")
            print(f"      Country: {data.get('cn', 'N/A')}")
            print(f"      ASN: {data.get('asn', {}).get('asn', 'N/A')}")
            print(f"      Org: {data.get('asn', {}).get('name', 'N/A')}")
            
        return True
    except Exception as e:
        print(f"❌ Error loading JSON: {e}")
        return False

def validate_csvs(csv_directory):
    """Validate and preview CSV files"""
    print("\n" + "="*70)
    print("2. Validating CSV Files")
    print("="*70)
    
    csv_directory = Path(csv_directory)
    
    if not csv_directory.exists():
        print(f"❌ CSV directory not found: {csv_directory}")
        return False
    
    print(f"✅ CSV directory exists: {csv_directory}")
    
    # Find CSV files (including subdirectories)
    csv_files = sorted(glob.glob(str(csv_directory / "**/*.csv"), recursive=True))
    
    if not csv_files:
        print(f"❌ No CSV files found in {csv_directory}")
        return False
    
    print(f"✅ Found {len(csv_files)} CSV files")
    
    # Calculate total size
    total_size = sum(Path(f).stat().st_size for f in csv_files)
    print(f"   Total size: {total_size / (1024**3):.2f} GB")
    
    # Preview first CSV
    print(f"\n   Preview of first CSV: {Path(csv_files[0]).name}")
    try:
        df = pd.read_csv(csv_files[0], nrows=5)
        print(f"\n   Columns: {list(df.columns)}")
        print(f"   Sample rows:")
        print(df.to_string(index=False))
        
        # Count total rows in first file
        row_count = sum(1 for _ in open(csv_files[0])) - 1  # -1 for header
        print(f"\n   Rows in this file: {row_count:,}")
        
        return True
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return False

def estimate_conversion(csv_directory, json_path):
    """Estimate conversion time and output size"""
    print("\n" + "="*70)
    print("3. Conversion Estimates")
    print("="*70)
    
    csv_files = sorted(glob.glob(str(Path(csv_directory) / "**/*.csv"), recursive=True))
    total_size_gb = sum(Path(f).stat().st_size for f in csv_files) / (1024**3)
    
    # Rough estimates
    # CSV to Parquet typically reduces size by 5-10x with snappy compression
    estimated_parquet_size = total_size_gb / 7  # Conservative estimate
    
    # Processing speed: ~100MB/sec for conversion
    estimated_minutes = (total_size_gb * 1024) / 100 / 60
    
    print(f"📊 Estimates:")
    print(f"   Input CSV size: {total_size_gb:.2f} GB")
    print(f"   Estimated Parquet size: {estimated_parquet_size:.2f} GB")
    print(f"   Estimated conversion time: {estimated_minutes:.1f} minutes")
    print(f"   Size reduction: ~{100 - (estimated_parquet_size/total_size_gb*100):.0f}%")

def test_conversion(json_path, csv_directory, output_directory):
    """Test conversion on a small sample"""
    print("\n" + "="*70)
    print("4. Test Conversion (First 10,000 rows)")
    print("="*70)
    
    try:
        # Import the converter
        sys.path.insert(0, str(Path(__file__).parent))
        from convert_to_parquet_v2 import AttackDataConverter
        
        output_test = Path(output_directory) / "test_output"
        output_test.mkdir(parents=True, exist_ok=True)
        
        print("Creating converter...")
        converter = AttackDataConverter(json_path, csv_directory, output_test)
        
        # Get first CSV (search recursively)
        csv_files = sorted(glob.glob(str(Path(csv_directory) / "**/*.csv"), recursive=True))
        if not csv_files:
            print("No CSV files found")
            return False
        
        print(f"Processing first 10,000 rows from {Path(csv_files[0]).name}...")
        
        # Process just the first chunk
        for i, chunk in enumerate(converter.process_csv_file(csv_files[0], chunk_size=10000)):
            if i == 0:  # Only process first chunk
                # Preview the enriched data
                print("\n✅ Enrichment successful!")
                print("\nSample enriched data (first 3 rows):")
                print("\nCore fields:")
                print(chunk[['datetime', 'IP', 'Time', 'Node', 'Port', 'Username']].head(3).to_string(index=False))
                print("\nGeo enrichment:")
                print(chunk[['IP', 'country', 'latitude', 'longitude']].head(3).to_string(index=False))
                print("\nASN enrichment:")
                print(chunk[['IP', 'asn', 'asn_name', 'asn_type']].head(3).to_string(index=False))
                print(f"\nTotal columns in output: {len(chunk.columns)}")
                print(f"All columns: {list(chunk.columns)}")
                
                # Save test file
                test_file = output_test / "test_sample.parquet"
                chunk.to_parquet(test_file, compression='snappy')
                
                test_size = test_file.stat().st_size
                print(f"\n✅ Test Parquet created: {test_file}")
                print(f"   Size: {test_size / 1024:.2f} KB for 10,000 rows")
                
                # Calculate compression ratio
                csv_size = Path(csv_files[0]).stat().st_size / (sum(1 for _ in open(csv_files[0])) - 1) * 10000
                compression_ratio = csv_size / test_size
                print(f"   Compression ratio: {compression_ratio:.1f}x")
                
                break
        
        return True
        
    except Exception as e:
        print(f"❌ Test conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main validation function"""
    print("="*70)
    print("Attack Data Pipeline - Validation & Test")
    print("="*70)
    
    # Prompt for paths
    print("\nPlease provide the following paths:")
    json_path = input("Path to JSON file: ").strip()
    csv_directory = input("Path to CSV directory: ").strip()
    output_directory = input("Path for output (press Enter for './parquet_output'): ").strip()
    
    if not output_directory:
        output_directory = "./parquet_output"
    
    # Run validations
    all_valid = True
    
    if not validate_json(json_path):
        all_valid = False
    
    if not validate_csvs(csv_directory):
        all_valid = False
    
    if all_valid:
        estimate_conversion(csv_directory, json_path)
        
        print("\n" + "="*70)
        print("Ready for Conversion!")
        print("="*70)
        
        test = input("\nRun test conversion on 10,000 rows? (y/n): ").strip().lower()
        if test == 'y':
            test_conversion(json_path, csv_directory, output_directory)
        
        print("\n" + "="*70)
        print("Next Steps:")
        print("="*70)
        print("1. Update paths in '01_convert_to_parquet.py'")
        print("2. Run: python 01_convert_to_parquet.py")
        print("   (This will process all 69 CSV files)")
        print("="*70)
    else:
        print("\n❌ Validation failed. Please fix the issues above.")

if __name__ == "__main__":
    main()
