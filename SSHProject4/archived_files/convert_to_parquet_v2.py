#!/usr/bin/env python3
"""
CSV to Parquet Conversion Pipeline (v2)
Uses configuration file for easy setup
"""

import json
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from tqdm import tqdm
import glob
from datetime import datetime
import configparser

class AttackDataConverter:
    def __init__(self, json_path, csv_directory, output_directory, chunk_size=100000, compression='snappy'):
        """
        Initialize the converter
        
        Args:
            json_path: Path to JSON file with IP info
            csv_directory: Directory containing CSV files
            output_directory: Where to save Parquet files
            chunk_size: Number of rows to process at once
            compression: Compression algorithm (snappy, gzip, etc.)
        """
        self.json_path = Path(json_path)
        self.csv_directory = Path(csv_directory)
        self.output_directory = Path(output_directory)
        self.chunk_size = chunk_size
        self.compression = compression
        self.output_directory.mkdir(parents=True, exist_ok=True)
        
        # Load IP lookup data
        print("Loading IP lookup data...")
        with open(self.json_path, 'r') as f:
            self.ip_data = json.load(f)
        print(f"✅ Loaded {len(self.ip_data):,} IP addresses")
        
    def enrich_row_with_ip_data(self, ip):
        """
        Enrich a row with IP geolocation and ASN data
        Returns a dict with all enrichment fields
        """
        def safe_float(value):
            """Safely convert to float, handling 'NaN' strings and invalid values"""
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                value = value.strip()
                if value.lower() in ('nan', 'none', '', 'null'):
                    return None
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None
            return None
        
        if ip in self.ip_data:
            ip_info = self.ip_data[ip]
            asn_info = ip_info.get('asn', {})
            
            return {
                'continent': ip_info.get('cntn', None),
                'country_code': ip_info.get('cc', None),
                'country': ip_info.get('cn', None),
                'latitude': safe_float(ip_info.get('lat')),
                'longitude': safe_float(ip_info.get('lng')),
                'asn': asn_info.get('asn', None),
                'asn_name': asn_info.get('name', None),
                'asn_domain': asn_info.get('domain', None),
                'asn_type': asn_info.get('type', None)
            }
        else:
            # Return None values for unknown IPs
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
    
    def process_csv_file(self, csv_path, chunk_size=None):
        """
        Process a single CSV file in chunks and yield enriched dataframes
        
        Args:
            csv_path: Path to CSV file
            chunk_size: Number of rows to process at once (uses self.chunk_size if None)
        """
        if chunk_size is None:
            chunk_size = self.chunk_size
            
        csv_path = Path(csv_path)
        
        # Read CSV in chunks to manage memory
        # low_memory=False ensures consistent column types
        for chunk in pd.read_csv(csv_path, chunksize=chunk_size, low_memory=False):
            # Convert Date to datetime (Date format: YYYYMMDD, Time is just a numeric field)
            chunk['datetime'] = pd.to_datetime(
                chunk['Date'].astype(str),
                format='%Y%m%d',
                errors='coerce'
            )
            
            # Extract year and month for partitioning
            chunk['year'] = chunk['datetime'].dt.year
            chunk['month'] = chunk['datetime'].dt.month
            
            # Fix data types for columns that may have mixed types
            # Convert numeric-looking columns to proper types
            chunk['Time'] = pd.to_numeric(chunk['Time'], errors='coerce').fillna(0).astype('int64')
            chunk['Port'] = pd.to_numeric(chunk['Port'], errors='coerce').fillna(0).astype('int64')
            
            # Ensure string columns are actually strings
            for col in ['IP', 'Node', 'PID', 'Username', 'Tag', 'Message']:
                chunk[col] = chunk[col].astype(str)
            
            # Enrich with IP data
            ip_enrichment = chunk['IP'].apply(self.enrich_row_with_ip_data)
            enrichment_df = pd.DataFrame(ip_enrichment.tolist())
            
            # Combine original data with enrichment
            enriched_chunk = pd.concat([chunk, enrichment_df], axis=1)
            
            # Drop the original Date column (keep Time as it's a separate field, not actual time)
            enriched_chunk = enriched_chunk.drop(columns=['Date'])
            
            # Reorder columns for better organization
            column_order = [
                'datetime', 'year', 'month', 'IP', 'Time',
                'continent', 'country_code', 'country', 'latitude', 'longitude',
                'asn', 'asn_name', 'asn_domain', 'asn_type',
                'Node', 'Port', 'PID', 'Username', 'Tag', 'Message'
            ]
            enriched_chunk = enriched_chunk[column_order]
            
            yield enriched_chunk
    
    def convert_all_csvs(self):
        """
        Convert all CSV files to partitioned Parquet format
        """
        # Find all CSV files (including in subdirectories)
        csv_files = sorted(glob.glob(str(self.csv_directory / "**/*.csv"), recursive=True))
        
        if not csv_files:
            print(f"❌ No CSV files found in {self.csv_directory}")
            return
        
        print(f"\n📂 Found {len(csv_files)} CSV files")
        print(f"💾 Output directory: {self.output_directory}")
        print(f"📦 Compression: {self.compression}")
        print(f"🔢 Chunk size: {self.chunk_size:,} rows\n")
        
        total_rows = 0
        start_time = datetime.now()
        
        # Process each CSV file with progress bar
        for csv_file in tqdm(csv_files, desc="Converting files", unit="file"):
            file_rows = 0
            
            for chunk in self.process_csv_file(csv_file):
                # Write partitioned by year and month
                for (year, month), group in chunk.groupby(['year', 'month']):
                    if pd.isna(year) or pd.isna(month):
                        partition_path = self.output_directory / "unknown"
                    else:
                        partition_path = self.output_directory / f"year={int(year)}" / f"month={int(month):02d}"
                    
                    partition_path.mkdir(parents=True, exist_ok=True)
                    
                    # Create unique filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    output_file = partition_path / f"data_{timestamp}.parquet"
                    
                    # Write to Parquet
                    table = pa.Table.from_pandas(group.drop(columns=['year', 'month']))
                    pq.write_table(table, output_file, compression=self.compression)
                    
                    file_rows += len(group)
                    total_rows += len(group)
        
        elapsed = datetime.now() - start_time
        
        print(f"\n{'='*70}")
        print(f"✅ Conversion Complete!")
        print(f"{'='*70}")
        print(f"Total rows processed: {total_rows:,}")
        print(f"Time elapsed: {elapsed}")
        print(f"Output location: {self.output_directory}")
        print(f"{'='*70}\n")
        
    def get_stats(self):
        """Get statistics about the converted data"""
        parquet_files = list(self.output_directory.rglob("*.parquet"))
        
        if not parquet_files:
            print("No Parquet files found")
            return
        
        print(f"\n📊 Conversion Statistics:")
        print(f"{'='*70}")
        print(f"Total Parquet files: {len(parquet_files)}")
        
        total_size = sum(f.stat().st_size for f in parquet_files)
        print(f"Total size: {total_size / (1024**3):.2f} GB")
        
        # Count partitions
        partitions = set()
        for f in parquet_files:
            parts = f.parts
            for i, part in enumerate(parts):
                if part.startswith('year='):
                    if i+1 < len(parts) and parts[i+1].startswith('month='):
                        partitions.add(f"{part}/{parts[i+1]}")
        
        print(f"Date partitions: {len(partitions)}")
        print("\nPartitions created:")
        for partition in sorted(partitions):
            print(f"  📅 {partition}")
        print(f"{'='*70}\n")


def load_config(config_path='config.ini'):
    """Load configuration from INI file"""
    config = configparser.ConfigParser()
    
    if not Path(config_path).exists():
        print(f"❌ Config file not found: {config_path}")
        return None
    
    config.read(config_path)
    return config


def main():
    """Main execution function"""
    print("="*70)
    print("Attack Log Data Conversion Pipeline")
    print("CSV → Parquet with IP Enrichment")
    print("="*70)
    
    # Load configuration
    config = load_config('config.ini')
    
    if config is None:
        print("\n❌ Please create a config.ini file with your paths")
        print("See config.ini.template for an example")
        return
    
    # Get paths from config
    try:
        json_path = config['paths']['json_file']
        csv_directory = config['paths']['csv_directory']
        output_directory = config['paths']['output_directory']
        chunk_size = int(config['processing']['chunk_size'])
        compression = config['processing']['compression']
    except KeyError as e:
        print(f"❌ Missing configuration key: {e}")
        return
    
    # Validate paths
    if not Path(json_path).exists():
        print(f"\n❌ JSON file not found: {json_path}")
        print("Please update the json_file path in config.ini")
        return
    
    if not Path(csv_directory).exists():
        print(f"\n❌ CSV directory not found: {csv_directory}")
        print("Please update the csv_directory path in config.ini")
        return
    
    # Create converter
    converter = AttackDataConverter(
        json_path=json_path,
        csv_directory=csv_directory,
        output_directory=output_directory,
        chunk_size=chunk_size,
        compression=compression
    )
    
    # Convert all CSVs
    converter.convert_all_csvs()
    
    # Show statistics
    converter.get_stats()
    
    print("Next Steps:")
    print("  1. Run: python 02_setup_duckdb.py")
    print("  2. This will create a DuckDB database for fast queries")
    print("="*70)


if __name__ == "__main__":
    main()