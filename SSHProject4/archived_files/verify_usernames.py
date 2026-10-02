"""
Verify dashboard discovery mode for a set of selected usernames.

For each chart it asks the running Flask API what it returns for
`usernames=...` (|||-separated, as dashboard.html sends it), then asks the
database directly what the answer SHOULD be, and compares the entities shown
and each entity's total attacks.

What each chart should show for the selected usernames:
    Total attacks  - the combined attacks on the selected usernames
    Countries      - the top countries attacking those usernames (1 to 10 of them)
    ASNs           - the top 10 ASNs attacking those usernames
    IPs            - the top 10 IPs attacking those usernames
    Usernames      - the selected usernames themselves

Usage (run from the backend folder, with Flask running on port 5000).
Pass each username as its own quoted argument. Usernames are matched exactly,
including any spaces or commas inside them:
    python verify_usernames.py "root" "admin" "ubuntu" "test"
"""

import sys
import json
import urllib.request
import urllib.parse
import urllib.error

from utils.db import get_db

API = 'http://localhost:5000/api'
START, END = '2022-11-01', '2023-01-08'


def api_totals(endpoint, key, usernames):
    """Call the API like dashboard.html does; sum attacks per entity across all dates."""
    qs = urllib.parse.urlencode({'start': START, 'end': END, 'usernames': '|||'.join(usernames)})
    rows = json.load(urllib.request.urlopen(f"{API}/{endpoint}?{qs}"))
    totals = {}
    for r in rows:
        name = r[key] if key else 'TOTAL'
        totals[name] = totals.get(name, 0) + r['attacks']
    return totals


def db_totals(column, table, usernames, limit=10):
    """What the chart SHOULD show: top `limit` entities among the selected usernames.
    Username data only exists in daily_ip_username_attacks, so every check uses it."""
    ph = ', '.join('?' * len(usernames))
    group = f"{column}, " if column else ""
    sql = f"""
        SELECT {column if column else "'TOTAL'"} AS name, SUM(attacks) AS total
        FROM {table}
        WHERE date BETWEEN ? AND ? AND username IN ({ph})
        {"GROUP BY " + column if column else ""}
        ORDER BY total DESC
        {f"LIMIT {limit}" if limit else ""}
    """
    conn = get_db()
    rows = conn.execute(sql, [START, END, *usernames]).fetchall()
    conn.close()
    return {name: int(total) for name, total in rows}


def compare(label, got, expected):
    missing = set(expected) - set(got)      # should be on the chart but isn't
    extra = set(got) - set(expected)        # on the chart but shouldn't be
    wrong = {k: (got[k], expected[k]) for k in set(got) & set(expected) if int(got[k]) != expected[k]}

    ok = not (missing or extra or wrong)
    print(f"\n{'✅ PASS' if ok else '❌ FAIL'}  {label}  ({len(got)} shown, {len(expected)} expected)")

    # Side-by-side table, ranked by what the database says, so you can match it
    # against the totals in the dashboard legend.
    names = sorted(set(got) | set(expected), key=lambda k: -expected.get(k, got.get(k, 0)))
    width = max([len(str(n)) for n in names] + [6])
    print(f"     {'#':>2}  {'Entity':<{width}}  {'Chart (API)':>14}  {'Database':>14}")
    for i, name in enumerate(names, 1):
        g = f"{int(got[name]):,}" if name in got else "— not shown —"
        e = f"{expected[name]:,}" if name in expected else "— not top 10 —"
        flag = "" if (name in got and name in expected and int(got[name]) == expected[name]) else "  ⟵"
        print(f"     {i:>2}  {str(name):<{width}}  {g:>14}  {e:>14}{flag}")
    for k in sorted(missing, key=lambda k: -expected[k]):
        print(f"     missing: {k}  (should be {expected[k]:,})")
    for k in sorted(extra, key=str):
        print(f"     extra:   {k}  (chart shows {int(got[k]):,})")
    for k, (g, e) in sorted(wrong.items(), key=lambda kv: str(kv[0])):
        print(f"     wrong total: {k}  chart {int(g):,} vs db {e:,}")
    return ok


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    # Not stripped: a leading/trailing space can be part of a real SSH username
    usernames = [u for u in sys.argv[1:] if u != '']
    print(f"Checking {len(usernames)} usernames, {START} to {END}")
    for u in usernames:
        print(f"   - {u!r}")

    checks = [
        # label,                   endpoint,           response key, db column,  db table,                     limit
        ("1. Total attacks",       'total_attacks',    None,         None,       'daily_ip_username_attacks',  None),
        ("2. Countries",           'country_attacks',  'country',    'country',  'daily_ip_username_attacks',  10),
        ("3. Top 10 ASNs",         'asn_attacks',      'asn_name',   'asn_name', 'daily_ip_username_attacks',  10),
        ("4. Top 10 IPs",          'ip_attacks',       'IP',         'IP',       'daily_ip_username_attacks',  10),
        ("5. Usernames (selected)",'username_attacks', 'username',   'username', 'daily_ip_username_attacks',  10),
    ]

    # Hit the API for everything first, then the database, so the two never
    # hold the DuckDB file at the same time.
    api_results = {}
    for label, endpoint, key, *_ in checks:
        try:
            api_results[label] = api_totals(endpoint, key, usernames)
        except urllib.error.URLError as e:
            api_results[label] = e

    passed = 0
    for label, endpoint, key, column, table, limit in checks:
        got = api_results[label]
        if isinstance(got, Exception):
            print(f"\n⚠️  ERROR  {label}: could not call /api/{endpoint} ({got})")
            continue
        try:
            expected = db_totals(column, table, usernames, limit)
        except Exception as e:
            print(f"\n⚠️  ERROR  {label}: could not query the database ({e})")
            if 'lock' in str(e).lower():
                print("     The database is locked by the Flask process, usually because an endpoint")
                print("     crashed above and left its connection open. Restart Flask and run again.")
            continue
        passed += compare(label, got, expected)

    print(f"\n{passed}/{len(checks)} checks passed")


if __name__ == '__main__':
    main()
