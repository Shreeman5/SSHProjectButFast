#!/usr/bin/env python3
"""
Side-by-side comparison with Max Percentage Change for Volatile ASNs
UPDATED: Uses batch call for Option A calculation
"""

import requests
from collections import Counter, defaultdict

API_BASE = "http://localhost:5000/api"
START_DATE = "2022-11-01"
END_DATE = "2023-01-08"


def get_top_volatile_countries():
    """Get top 10 volatile countries"""
    print("Fetching top 10 volatile countries...")
    url = f"{API_BASE}/unusual_countries?start={START_DATE}&end={END_DATE}"
    response = requests.get(url)
    data = response.json()
    
    country_totals = Counter()
    for row in data:
        country_totals[row['country']] += row['attacks']
    
    top_10 = [country for country, _ in country_totals.most_common(10)]
    print(f"Top 10 volatile countries: {top_10}\n")
    return top_10


def get_attacking_asns(countries):
    """Get attacking ASNs from given countries"""
    print("Fetching ATTACKING ASNs from volatile countries...")
    all_data = []
    
    for country in countries:
        url = f"{API_BASE}/asn_attacks?start={START_DATE}&end={END_DATE}&country={country}"
        response = requests.get(url)
        data = response.json()
        all_data.extend(data)
    
    asn_totals = Counter()
    for row in all_data:
        asn_totals[row['asn_name']] += row['attacks']
    
    print(f"  → Found {len(asn_totals)} unique attacking ASNs\n")
    return asn_totals


def get_volatile_asns_with_pct_change(countries):
    """Get volatile ASNs with their max percentage change - OPTION A (batch call)"""
    print("Fetching VOLATILE ASNs from volatile countries (Option A - batch call)...")
    
    # UPDATED: Use batch call with ||| delimiter
    countries_param = '|||'.join(countries)
    url = f"{API_BASE}/asn_attacks_volatile?start={START_DATE}&end={END_DATE}&countries={countries_param}"
    
    print(f"  → Calling: {url[:100]}...")
    
    try:
        response = requests.get(url)
        print(f"  → Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"  → Response text: {response.text[:500]}")
            return Counter(), {}
        
        data = response.json()
    except Exception as e:
        print(f"  → Error fetching data: {e}")
        print(f"  → Response text: {response.text[:500]}")
        return Counter(), {}
    
    # Track total attacks and max pct_change per ASN
    asn_totals = Counter()
    asn_max_pct = {}
    
    for row in data:
        asn_name = row['asn_name']
        asn_totals[asn_name] += row['attacks']
        
        # Track max percentage change
        if 'pct_change' in row and row['pct_change'] is not None:
            if asn_name not in asn_max_pct:
                asn_max_pct[asn_name] = abs(row['pct_change'])  # Use absolute value
            else:
                asn_max_pct[asn_name] = max(asn_max_pct[asn_name], abs(row['pct_change']))
    
    print(f"  → Found {len(asn_totals)} unique volatile ASNs")
    print(f"  → {len(asn_max_pct)} ASNs have pct_change data\n")
    
    return asn_totals, asn_max_pct


def print_side_by_side_with_pct(attacking_asns, volatile_asns, volatile_pct_change, num_rows=50):
    """Print comparison with percentage change"""
    print("=" * 175)
    print("SIDE-BY-SIDE COMPARISON: Attacking (by Total Attacks) vs Volatile (by Max % Change)")
    print("=" * 175)
    
    # Get top N attacking (by attacks)
    top_attacking = attacking_asns.most_common(num_rows)
    
    # Get top N volatile (by MAX % CHANGE - this is what frontend should show)
    asns_with_pct = [(asn, attacks, volatile_pct_change[asn]) 
                     for asn, attacks in volatile_asns.items() 
                     if asn in volatile_pct_change]
    top_volatile_by_pct = sorted(asns_with_pct, key=lambda x: x[2], reverse=True)[:num_rows]
    
    # Print header
    print(f"{'RANK':<5} {'ATTACKING ASNs (by attacks)':<40} {'ATTACKS':<12} | {'VOLATILE ASNs (by max %Δ)':<40} {'ATTACKS':<12} {'MAX %Δ':<12}")
    print("-" * 175)
    
    # Print rows
    for i in range(num_rows):
        rank = i + 1
        
        # Attacking side
        if i < len(top_attacking):
            att_asn, att_attacks = top_attacking[i]
            att_asn_str = att_asn[:37] + "..." if len(att_asn) > 40 else att_asn
            att_attacks_str = f"{att_attacks:,}"
        else:
            att_asn_str = "-"
            att_attacks_str = "-"
        
        # Volatile side (ranked by % change)
        if i < len(top_volatile_by_pct):
            vol_asn, vol_attacks, vol_pct = top_volatile_by_pct[i]
            vol_asn_str = vol_asn[:37] + "..." if len(vol_asn) > 40 else vol_asn
            vol_attacks_str = f"{vol_attacks:,}"
            pct_str = f"{vol_pct:.1f}%"
        else:
            vol_asn_str = "-"
            vol_attacks_str = "-"
            pct_str = "-"
        
        # Print row
        print(f"{rank:<5} {att_asn_str:<40} {att_attacks_str:<12} | {vol_asn_str:<40} {vol_attacks_str:<12} {pct_str:<12}")


def print_volatile_ranking_info(volatile_asns, volatile_pct_change):
    """Show how volatile ASNs should be ranked"""
    print("\n" + "=" * 175)
    print("VOLATILE ASN RANKING - WHAT FRONTEND SHOULD SHOW")
    print("=" * 175)
    
    print("\n❌ WRONG: If ranked by TOTAL ATTACKS (old behavior):")
    top_by_attacks = volatile_asns.most_common(10)
    for i, (asn, attacks) in enumerate(top_by_attacks, 1):
        pct = volatile_pct_change.get(asn, None)
        pct_str = f"{pct:.1f}%" if pct is not None else "N/A"
        print(f"  {i}. {asn}: {attacks:,} attacks, Max %Δ: {pct_str}")
    
    print("\n✅ CORRECT: Ranked by MAX % CHANGE (new behavior):")
    asns_with_pct = [(asn, attacks, volatile_pct_change[asn]) 
                     for asn, attacks in volatile_asns.items() 
                     if asn in volatile_pct_change]
    top_by_pct = sorted(asns_with_pct, key=lambda x: x[2], reverse=True)[:10]
    
    for i, (asn, attacks, pct) in enumerate(top_by_pct, 1):
        print(f"  {i}. {asn}: {attacks:,} attacks, Max %Δ: {pct:.1f}%")
    
    # Check if ranking is same
    attacks_ranking = [asn for asn, _ in top_by_attacks]
    pct_ranking = [asn for asn, _, _ in top_by_pct]
    
    print("\n" + "-" * 80)
    if attacks_ranking == pct_ranking:
        print("✅ Rankings are IDENTICAL - order doesn't matter")
    else:
        print("❌ Rankings are DIFFERENT")
        overlap = set(attacks_ranking) & set(pct_ranking)
        print(f"  → ASNs in both top 10: {len(overlap)}")
        print(f"  → Only in attacks ranking: {set(attacks_ranking) - set(pct_ranking)}")
        print(f"  → Only in %Δ ranking: {set(pct_ranking) - set(attacks_ranking)}")
        
    print("\n💡 Your UI should match the '✅ CORRECT' list above!")


def print_statistics(attacking_asns, volatile_asns, volatile_pct_change):
    """Print summary statistics"""
    print("\n" + "=" * 175)
    print("SUMMARY STATISTICS")
    print("=" * 175)
    
    # Get correct volatile ranking (by max % change)
    asns_with_pct = [(asn, attacks, volatile_pct_change[asn]) 
                     for asn, attacks in volatile_asns.items() 
                     if asn in volatile_pct_change]
    top_10_volatile_by_pct = [asn for asn, _, _ in sorted(asns_with_pct, key=lambda x: x[2], reverse=True)[:10]]
    
    # Top 10 sets
    top_10_attacking = set([asn for asn, _ in attacking_asns.most_common(10)])
    top_10_volatile = set(top_10_volatile_by_pct)
    
    # Overlap
    overlap = top_10_attacking & top_10_volatile
    only_attacking = top_10_attacking - top_10_volatile
    only_volatile = top_10_volatile - top_10_attacking
    
    print(f"\nTotal unique attacking ASNs: {len(attacking_asns)}")
    print(f"Total unique volatile ASNs: {len(volatile_asns)}")
    print(f"Volatile ASNs with pct_change data: {len(volatile_pct_change)}")
    
    print(f"\n--- Top 10 Overlap Analysis (Attacking vs Volatile by Max %Δ) ---")
    print(f"ASNs in BOTH top 10 lists: {len(overlap)}")
    if overlap:
        print("\nShared ASNs:")
        for asn in overlap:
            att_attacks = attacking_asns[asn]
            vol_attacks = volatile_asns[asn]
            pct = volatile_pct_change.get(asn, None)
            pct_str = f"{pct:.1f}%" if pct is not None else "N/A"
            att_rank = [i for i, (a, _) in enumerate(attacking_asns.most_common(50), 1) if a == asn][0]
            vol_rank = top_10_volatile_by_pct.index(asn) + 1 if asn in top_10_volatile_by_pct else "?"
            print(f"  → {asn}")
            print(f"     Attacking: #{att_rank}, {att_attacks:,} attacks")
            print(f"     Volatile:  #{vol_rank}, {vol_attacks:,} attacks, Max %Δ: {pct_str}")
    
    print(f"\nASNs ONLY in top 10 attacking ({len(only_attacking)}):")
    if only_attacking:
        for asn in list(only_attacking)[:5]:
            att_rank = [i for i, (a, _) in enumerate(attacking_asns.most_common(50), 1) if a == asn][0]
            print(f"  → {asn}: #{att_rank} in attacking, {attacking_asns[asn]:,} attacks")
        if len(only_attacking) > 5:
            print(f"  ... and {len(only_attacking) - 5} more")
    
    print(f"\nASNs ONLY in top 10 volatile ({len(only_volatile)}):")
    if only_volatile:
        for asn in list(only_volatile)[:5]:
            pct = volatile_pct_change.get(asn, None)
            pct_str = f"{pct:.1f}%" if pct is not None else "N/A"
            vol_rank = top_10_volatile_by_pct.index(asn) + 1
            print(f"  → {asn}: #{vol_rank} in volatile, {volatile_asns[asn]:,} attacks, Max %Δ: {pct_str}")
        if len(only_volatile) > 5:
            print(f"  ... and {len(only_volatile) - 5} more")
    
    # Total attacks
    total_attacking = sum(attacking_asns.values())
    total_volatile = sum(volatile_asns.values())
    
    print(f"\n--- Attack Volume ---")
    print(f"Total attacking attacks: {total_attacking:,}")
    print(f"Total volatile attacks: {total_volatile:,}")
    print(f"Volatile as % of attacking: {100 * total_volatile / total_attacking:.2f}%")


def main():
    try:
        # Get top 10 volatile countries
        countries = get_top_volatile_countries()
        
        # Get attacking ASNs
        attacking_asns = get_attacking_asns(countries)
        
        # Get volatile ASNs with pct_change (using batch call - Option A)
        volatile_asns, volatile_pct_change = get_volatile_asns_with_pct_change(countries)
        
        if not volatile_asns:
            print("ERROR: No volatile ASN data returned. Check backend logs.")
            return
        
        # Print side-by-side comparison
        print_side_by_side_with_pct(attacking_asns, volatile_asns, volatile_pct_change, num_rows=50)
        
        # Show ranking analysis
        print_volatile_ranking_info(volatile_asns, volatile_pct_change)
        
        # Print statistics
        print_statistics(attacking_asns, volatile_asns, volatile_pct_change)
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to API. Make sure Flask server is running on localhost:5000")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()