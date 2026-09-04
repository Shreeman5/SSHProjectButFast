#!/usr/bin/env python3
"""
Quick test to verify ASN API returns new columns
"""

import requests
import json

url = "http://localhost:5000/api/asn_summary?start=2022-11-01&end=2023-01-08&limit=1"

print("Testing ASN API endpoint...")
print(f"URL: {url}\n")

response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    
    if len(data) > 0:
        asn = data[0]
        
        print(f"✅ API Response OK!\n")
        print(f"ASN Name: {asn.get('asn_name')}")
        print(f"Total Attacks: {asn.get('total_attacks'):,}")
        print(f"\n📊 NEW STABILITY COLUMNS:")
        print(f"   Unique Countries: {asn.get('unique_countries')}")
        print(f"   Primary Country: {asn.get('primary_country')}")
        print(f"   Unique IPs: {asn.get('unique_ips')}")
        print(f"   Unique Usernames: {asn.get('unique_usernames')}")
        print(f"   Country Concentration: {asn.get('country_concentration')}")
        print(f"   IP Concentration: {asn.get('ip_concentration')}")
        print(f"   Username Concentration: {asn.get('username_concentration')}")
        print(f"   Country Rotation: {asn.get('country_rotation')}")
        print(f"   IP Rotation: {asn.get('ip_rotation')}")
        print(f"   Username Rotation: {asn.get('username_rotation')}")
        print(f"   Country Stability: {asn.get('country_stability')}")
        print(f"   IP Stability: {asn.get('ip_stability')}")
        print(f"   Username Stability: {asn.get('username_stability')}")
        
        # Check if any new columns are present
        new_columns = ['unique_countries', 'unique_ips', 'country_concentration', 'ip_stability']
        has_new_data = any(asn.get(col) is not None for col in new_columns)
        
        if has_new_data:
            print(f"\n✅ SUCCESS! New stability columns are present and have data!")
        else:
            print(f"\n⚠️  WARNING! New columns exist but have NULL values - may need to verify table join")
    else:
        print("⚠️  No data returned")
else:
    print(f"❌ API Error: {response.status_code}")
    print(response.text)
