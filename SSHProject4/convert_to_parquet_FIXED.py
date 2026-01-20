#!/usr/bin/env python3
"""
CSV to Parquet Conversion with IP Enrichment - FIXED VERSION
Ensures ALL chunks are enriched, not just first chunk per CSV
"""

import pandas as pd
import json
from pathlib import Path
import configparser
from tqdm import tqdm

class CSVToParquetConverter:
    def __init__(self, json_path, csv_directory, output_directory, chunk_size=100000, compression='snappy'):
        """
        Initialize converter with IP enrichment
        """
        self.json_path = Path(json_path)
        self.csv_directory = Path(csv_directory)
        self.output_directory = Path(output_directory)
        self.chunk_size = chunk_size
        self.compression = compression
        
        # Load IP enrichment data
        print(f"Loading IP lookup data from {json_path}...")
        with open(self.json_path, 'r') as f:
            self.ip_data = json.load(f)
        print(f"✅ Loaded {len(self.ip_data):,} IP addresses")
        
    def enrich_row_with_ip_data(self, ip):
        """Enrich a row with IP geolocation and ASN data"""
        
        def safe_float(value):
            """Safely convert to float"""
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
        
        # Return default values if IP not in lookup
        if ip not in self.ip_data:
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
    
    def process_csv_file(self, csv_path):
        """
        Process a single CSV file in chunks and yield enriched dataframes
        FIXED: Enriches EVERY chunk, not just first one
        """
        csv_path = Path(csv_path)
        
        # Read CSV in chunks
        chunk_num = 0
        enriched_chunks = 0
        
        for chunk in pd.read_csv(csv_path, chunksize=self.chunk_size, low_memory=False):
            chunk_num += 1
            
            # Convert datetime
            chunk['datetime'] = pd.to_datetime(
                chunk['Date'].astype(str), 
                format='%Y%m%d', 
                errors='coerce'
            )
            
            # Extract year and month for partitioning
            chunk['year'] = chunk['datetime'].dt.year
            chunk['month'] = chunk['datetime'].dt.month
            
            # Fix data types
            chunk['Time'] = pd.to_numeric(chunk['Time'], errors='coerce').fillna(0).astype('int64')
            chunk['Port'] = pd.to_numeric(chunk['Port'], errors='coerce').fillna(0).astype('int64')
            
            # Ensure string columns are strings
            for col in ['IP', 'Node', 'PID', 'Username', 'Tag', 'Message']:
                chunk[col] = chunk[col].astype(str)
            
            # **CRITICAL: Enrich with IP data for EVERY chunk**
            try:
                print(f"      Enriching chunk {chunk_num} ({len(chunk)} rows)...")
                ip_enrichment = chunk['IP'].apply(self.enrich_row_with_ip_data)
                enrichment_df = pd.DataFrame(ip_enrichment.tolist(), index=chunk.index)  # FIX: Preserve index!
                
                # Verify enrichment worked
                non_null_country = enrichment_df['country'].notna().sum()
                print(f"      ✅ Enriched: {non_null_country}/{len(chunk)} rows have country data")
                
                if non_null_country == 0:
                    print(f"      ⚠️  WARNING: No IPs matched in lookup for this chunk!")
                else:
                    enriched_chunks += 1
                
                # Combine original data with enrichment
                enriched_chunk = pd.concat([chunk, enrichment_df], axis=1)
                
            except Exception as e:
                print(f"      ❌ ERROR enriching chunk {chunk_num}: {e}")
                print(f"      Continuing without enrichment for this chunk...")
                # Create empty enrichment columns
                enriched_chunk = chunk.copy()
                for col in ['continent', 'country_code', 'country', 'latitude', 'longitude', 
                           'asn', 'asn_name', 'asn_domain', 'asn_type']:
                    enriched_chunk[col] = None
            
            # Drop the original Date column
            enriched_chunk = enriched_chunk.drop(columns=['Date'])
            
            # Reorder columns
            column_order = [
                'datetime', 'year', 'month', 'IP', 'Time',
                'continent', 'country_code', 'country', 'latitude', 'longitude',
                'asn', 'asn_name', 'asn_domain', 'asn_type',
                'Node', 'Port', 'PID', 'Username', 'Tag', 'Message'
            ]
            enriched_chunk = enriched_chunk[column_order]
            
            yield enriched_chunk
        
        print(f"   📊 Total chunks: {chunk_num}, Successfully enriched: {enriched_chunks}")
    
    def convert(self):
        """Convert all CSV files to partitioned Parquet with IP enrichment"""
        
        # Find all CSV files
        csv_files = list(self.csv_directory.glob('*/*.csv'))
        
        if not csv_files:
            print("❌ No CSV files found")
            return
        
        print(f"\n📂 Found {len(csv_files)} CSV files")
        print(f"📦 Output directory: {self.output_directory}")
        print(f"🗜️  Compression: {self.compression}")
        print(f"📏 Chunk size: {self.chunk_size:,} rows")
        
        # Create output directory
        self.output_directory.mkdir(parents=True, exist_ok=True)
        
        total_rows = 0
        total_files_written = 0
        
        # Process each CSV file
        for csv_file in tqdm(csv_files, desc="Converting files"):
            print(f"\n📄 Processing: {csv_file.name}")
            
            file_rows = 0
            file_chunks = 0
            
            try:
                # Process CSV in chunks and write to partitioned Parquet
                for enriched_chunk in self.process_csv_file(csv_file):
                    
                    # Group by partition (year, month)
                    for (year, month), group in enriched_chunk.groupby(['year', 'month']):
                        
                        # Create partition directory
                        partition_dir = self.output_directory / f"year={int(year)}" / f"month={int(month)}"
                        partition_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Generate unique filename
                        import time
                        timestamp = int(time.time() * 1000000)
                        output_file = partition_dir / f"data_{csv_file.stem}_{timestamp}_{file_chunks}.parquet"
                        
                        # Write to Parquet
                        group.to_parquet(
                            output_file,
                            engine='pyarrow',
                            compression=self.compression,
                            index=False
                        )
                        
                        file_rows += len(group)
                        file_chunks += 1
                        total_files_written += 1
                
                total_rows += file_rows
                print(f"   ✅ Wrote {file_rows:,} rows in {file_chunks} chunks")
                
            except Exception as e:
                print(f"   ❌ Error processing {csv_file.name}: {e}")
                continue
        
        print("\n" + "="*70)
        print("Conversion Complete!")
        print("="*70)
        print(f"✅ Total rows processed: {total_rows:,}")
        print(f"✅ Total Parquet files: {total_files_written}")
        print(f"📂 Output location: {self.output_directory}")
        print("="*70)


def main():
    """Main execution"""
    
    # Load configuration
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    try:
        json_path = config['paths']['json_file']
        csv_directory = config['paths']['csv_directory']
        output_directory = config['paths']['output_directory']
    except KeyError as e:
        print(f"❌ Config file missing required key: {e}")
        return
    
    # Verify JSON file exists
    if not Path(json_path).exists():
        print(f"\n❌ JSON file not found: {json_path}")
        print("Please update the json_file path in config.ini")
        return
    
    print("="*70)
    print("CSV → Parquet with IP Enrichment (FIXED VERSION)")
    print("="*70)
    
    # Create converter and run
    converter = CSVToParquetConverter(
        json_path=json_path,
        csv_directory=csv_directory,
        output_directory=output_directory,
        chunk_size=100000,
        compression='snappy'
    )
    
    converter.convert()


if __name__ == "__main__":
    main()