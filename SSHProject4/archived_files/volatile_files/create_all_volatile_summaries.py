#!/usr/bin/env python3
"""
Create All Volatile Summary Tables
Master script to build all 4 volatile summary tables
"""
import subprocess
import time

def run_script(script_name):
    """Run a script and report timing"""
    print(f"\n{'='*70}")
    print(f"Running {script_name}...")
    print(f"{'='*70}")
    
    start = time.time()
    result = subprocess.run(['python3', script_name], check=True)
    elapsed = time.time() - start
    
    print(f"\n✅ {script_name} completed in {elapsed:.1f} seconds")
    return elapsed

def main():
    print("="*70)
    print("CREATING ALL VOLATILE SUMMARY TABLES")
    print("="*70)
    print("\nThis will create 4 pre-computed volatile summary tables:")
    print("  1. volatile_country_summary")
    print("  2. volatile_ip_summary")
    print("  3. volatile_asn_summary")
    print("  4. volatile_username_summary")
    print("\nThese tables will make volatile chart queries MUCH faster!")
    print("="*70)
    
    scripts = [
        'create_volatile_country_summary.py',
        'create_volatile_ip_summary.py',
        'create_volatile_asn_summary.py',
        'create_volatile_username_summary.py'
    ]
    
    total_start = time.time()
    timings = {}
    
    for script in scripts:
        try:
            elapsed = run_script(script)
            timings[script] = elapsed
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Error running {script}: {e}")
            return
        except FileNotFoundError:
            print(f"\n❌ Script not found: {script}")
            print("Make sure all scripts are in the current directory!")
            return
    
    total_elapsed = time.time() - total_start
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("\nTiming breakdown:")
    for script, elapsed in timings.items():
        print(f"  {script:<45} {elapsed:>8.1f}s")
    print(f"\n{'Total time:':<45} {total_elapsed:>8.1f}s")
    
    print("\n" + "="*70)
    print("✅ ALL VOLATILE SUMMARY TABLES CREATED SUCCESSFULLY!")
    print("="*70)
    print("\nNext steps:")
    print("  1. The volatile endpoints will now use these pre-computed tables")
    print("  2. Charts should load much faster when toggled to volatile view")
    print("  3. Re-run these scripts if you add new data to the database")
    print("="*70)

if __name__ == "__main__":
    main()
