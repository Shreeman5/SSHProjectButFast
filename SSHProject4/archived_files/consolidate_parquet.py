#!/usr/bin/env python3
"""
Ultra-Minimal Parquet Consolidation
Processes ONE partition at a time to avoid memory issues
"""

import duckdb
from pathlib import Path
import configparser
import time
import gc

def consolidate_one_partition(partition_dir):
    """Consolidate a single partition directory"""
    
    parquet_files = list(partition_dir.glob("*.parquet"))
    
    if len(parquet_files) <= 1:
        return False, "Already consolidated or empty"
    
    if (partition_dir / "consolidated.parquet").exists():
        return False, "Already has consolidated file"
    
    print(f"\n📂 Processing: {partition_dir.name}")
    print(f"   Files: {len(parquet_files)}")
    
    try:
        # Create isolated connection for this partition only
        conn = duckdb.connect(':memory:')
        
        pattern = str(partition_dir / "*.parquet")
        temp_output = partition_dir / "temp_consolidated.parquet"
        final_output = partition_dir / "consolidated.parquet"
        
        # Stream data without loading into memory
        conn.execute(f"""
            COPY (
                SELECT * FROM read_parquet('{pattern}', union_by_name=true)
            ) TO '{temp_output}' (FORMAT PARQUET, COMPRESSION SNAPPY)
        """)
        
        conn.close()
        del conn
        gc.collect()  # Force garbage collection
        
        # Rename temp to final
        temp_output.rename(final_output)
        
        # Delete old files
        for pf in parquet_files:
            pf.unlink()
        
        print(f"   ✅ Consolidated successfully")
        return True, "Success"
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        # Cleanup
        if temp_output.exists():
            temp_output.unlink()
        return False, str(e)


def main():
    """Main execution"""
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    try:
        parquet_directory = Path(config['paths']['output_directory'])
    except KeyError:
        print("❌ Config file missing output_directory")
        return
    
    print("="*70)
    print("Ultra-Minimal Parquet Consolidation")
    print("One partition at a time - Very safe!")
    print("="*70)
    
    # Find all partitions
    partitions = []
    for year_dir in sorted(parquet_directory.glob("year=*")):
        for month_dir in sorted(year_dir.glob("month=*")):
            partitions.append(month_dir)
    
    if not partitions:
        print("❌ No partitions found")
        return
    
    print(f"\n📊 Found {len(partitions)} partitions")
    print(f"📂 Directory: {parquet_directory}\n")
    
    response = input("Start consolidation? (y/n): ").strip().lower()
    if response != 'y':
        print("Cancelled")
        return
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for i, partition_dir in enumerate(partitions, 1):
        print(f"\n[{i}/{len(partitions)}] {partition_dir.relative_to(parquet_directory)}")
        
        success, message = consolidate_one_partition(partition_dir)
        
        if success:
            success_count += 1
        elif "Already" in message:
            skip_count += 1
            print(f"   ⏭️  {message}")
        else:
            error_count += 1
        
        # Pause between partitions to let system breathe
        if i < len(partitions):
            time.sleep(0.5)
    
    print("\n" + "="*70)
    print("Consolidation Complete!")
    print("="*70)
    print(f"✅ Consolidated: {success_count}")
    print(f"⏭️  Skipped: {skip_count}")
    print(f"❌ Errors: {error_count}")
    print("="*70)
    
    if success_count > 0:
        print("\nNext Steps:")
        print("  1. Run: python api.py")
        print("  2. Open: dashboard.html")
        print("  3. Charts should load fast now!")


if __name__ == "__main__":
    main()