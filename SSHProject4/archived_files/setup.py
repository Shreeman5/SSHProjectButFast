#!/usr/bin/env python3
"""
Quick Setup Script
Helps you get started with the attack data pipeline
"""

import subprocess
import sys
from pathlib import Path

def check_python_version():
    """Check if Python version is adequate"""
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ required")
        return False
    
    print("✅ Python version OK")
    return True

def install_dependencies():
    """Install required Python packages"""
    print("\n" + "="*70)
    print("Installing Dependencies")
    print("="*70)
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("\n✅ All dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("\n❌ Failed to install dependencies")
        return False

def create_config_template():
    """Create a config file if it doesn't exist"""
    config_path = Path("config.ini")
    
    if config_path.exists():
        print("\n✅ config.ini already exists")
        return True
    
    print("\n📝 Creating config.ini template...")
    
    config_content = """# Configuration for Attack Data Pipeline
# UPDATE THESE PATHS BEFORE RUNNING THE CONVERSION

[paths]
# Path to your JSON file with IP location/ASN data
json_file = /path/to/your/ip_data.json

# Directory containing your CSV files
csv_directory = /path/to/your/csv_files/

# Where to save the converted Parquet files
output_directory = ./parquet_output

# Where to save the DuckDB database
duckdb_path = ./attack_data.db

[processing]
# Number of rows to process at once (adjust based on your RAM)
# 100000 = ~100MB per chunk for your data
chunk_size = 100000

# Compression for Parquet files (snappy is fast, gzip is smaller)
compression = snappy
"""
    
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    print("✅ Created config.ini")
    print("⚠️  IMPORTANT: Edit config.ini with your actual file paths!")
    return True

def print_next_steps():
    """Print what to do next"""
    print("\n" + "="*70)
    print("Setup Complete! Next Steps:")
    print("="*70)
    print("\n1. Edit config.ini with your actual file paths:")
    print("   - json_file: Path to your IP lookup JSON")
    print("   - csv_directory: Directory with your CSV files")
    print("   - output_directory: Where to save results")
    
    print("\n2. Validate your setup:")
    print("   python 00_validate_setup.py")
    
    print("\n3. Run the conversion:")
    print("   python convert_to_parquet_v2.py")
    
    print("\n4. (After conversion) Set up DuckDB:")
    print("   python 02_setup_duckdb.py")
    
    print("\n" + "="*70)
    print("Need help? Check README.md")
    print("="*70)

def main():
    """Main setup function"""
    print("="*70)
    print("Attack Data Pipeline - Setup")
    print("="*70)
    
    # Check Python version
    if not check_python_version():
        return
    
    # Install dependencies
    print("\nThis will install the following packages:")
    print("  - pandas")
    print("  - pyarrow")
    print("  - duckdb")
    print("  - tqdm")
    
    response = input("\nProceed with installation? (y/n): ").strip().lower()
    if response != 'y':
        print("Setup cancelled")
        return
    
    if not install_dependencies():
        return
    
    # Create config template
    create_config_template()
    
    # Print next steps
    print_next_steps()

if __name__ == "__main__":
    main()
