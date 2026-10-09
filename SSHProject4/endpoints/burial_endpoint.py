"""
Burial Endpoint
Chart 7: how far down the default views a searched IP (and the IPs sent with it) sits.

Register in app.py next to the other endpoints:

    from endpoints.burial_endpoint import register_burial
    register_burial(app)

GET /api/burial?start=...&end=...&searched=<ip>&ips=<ip>|||<ip>|||...

Everything is ranked by total attacks in the date range -- the same rule the
dashboard's Top 10 charts use to decide what is visible -- so "rank 4,812"
means "the 4,812th IP the volume-ranked views would show". Drill-down filters
(country, ASN, username...) are deliberately ignored: burial is measured
against the whole dataset.

Response, per level (country / ASN / IP):
    total, share (% of all attacks), rank, of (how many entities at that level),
    top10_share (share of the 10th-ranked entity: the default view's cutoff).

ASNs span countries, so the ASN level is ranked globally; the nested figures
(the ASN's share of the country, the IP's share of its ASN in that country,
and their ranks there) are returned alongside as `within`.
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params

LIST_SEP = '|||'
TOP_N = 10          # the dashboard's default chart size
MAX_IPS = 1000


def _ranked(conn, column, start, end, where='', params=()):
    """Every value of `column` with its total and rank (1 = most attacks)."""
    return conn.execute(f"""
        WITH t AS (
            SELECT {column} AS k, SUM(attacks) AS total
            FROM daily_ip_attacks
            WHERE date BETWEEN ? AND ? {where}
            GROUP BY {column}
        )
        SELECT k, total, RANK() OVER (ORDER BY total DESC) AS rk
        FROM t
        ORDER BY rk, k
    """, [start, end, *params]).fetchall()


def _level(rows, key, grand_total):
    """Summarise one level for entity `key` from _ranked() rows."""
    hit = next((r for r in rows if r[0] == key), None)
    tenth = rows[TOP_N - 1][1] if len(rows) >= TOP_N else (rows[-1][1] if rows else 0)
    return {
        'name': key,
        'total': int(hit[1]) if hit else 0,
        'share': (100.0 * hit[1] / grand_total) if hit and grand_total else 0.0,
        'rank': int(hit[2]) if hit else None,
        'of': len(rows),
        'top10_share': (100.0 * tenth / grand_total) if grand_total else 0.0,
        'in_top10': bool(hit and hit[2] <= TOP_N),
    }


def register_burial(app):
    """Register the burial endpoint"""

    @app.route('/api/burial', methods=['GET'])
    def get_burial():
        start, end = parse_date_params()
        searched = (request.args.get('searched') or '').strip()
        ips = [i.strip() for i in (request.args.get('ips') or '').split(LIST_SEP) if i.strip()]
        if not searched:
            return jsonify({'error': 'Missing searched parameter'}), 400
        if searched not in ips:
            ips = [searched] + ips
        ips = ips[:MAX_IPS]

        conn = get_db()
        try:
            grand = conn.execute("""
                SELECT SUM(attacks) FROM daily_ip_attacks WHERE date BETWEEN ? AND ?
            """, [start, end]).fetchone()[0] or 0

            # The searched IP's main country and ASN (where most of its attacks came from).
            home = conn.execute("""
                SELECT country, asn_name, SUM(attacks) AS s
                FROM daily_ip_attacks
                WHERE IP = ? AND date BETWEEN ? AND ?
                GROUP BY country, asn_name
                ORDER BY s DESC, country, asn_name
                LIMIT 1
            """, [searched, start, end]).fetchone()
            if not home:
                return jsonify({'error': f'{searched} has no attacks between {start} and {end}.'}), 404
            country, asn = home[0], home[1]

            countries = _ranked(conn, 'country', start, end)
            asns = _ranked(conn, 'asn_name', start, end)
            all_ips = _ranked(conn, 'IP', start, end)

            # Nested context: the ASN inside the country, the IP inside that ASN-in-country.
            asns_in_country = _ranked(conn, 'asn_name', start, end, 'AND country = ?', [country])
            ips_in_slice = _ranked(conn, 'IP', start, end, 'AND country = ? AND asn_name = ?', [country, asn])

            ph = ', '.join(['?'] * len(ips))
            ip_home = {r[0]: (r[1], r[2]) for r in conn.execute(f"""
                WITH x AS (
                    SELECT IP, country, asn_name, SUM(attacks) AS s
                    FROM daily_ip_attacks
                    WHERE IP IN ({ph}) AND date BETWEEN ? AND ?
                    GROUP BY IP, country, asn_name
                ),
                y AS (
                    SELECT IP, country, asn_name,
                           ROW_NUMBER() OVER (PARTITION BY IP ORDER BY s DESC, country, asn_name) AS rn
                    FROM x
                )
                SELECT IP, country, asn_name FROM y WHERE rn = 1
            """, [*ips, start, end]).fetchall()}
        finally:
            conn.close()

        country_lvl = _level(countries, country, grand)
        asn_lvl = _level(asns, asn, grand)
        ip_lvl = _level(all_ips, searched, grand)

        asn_in = next((r for r in asns_in_country if r[0] == asn), None)
        ip_in = next((r for r in ips_in_slice if r[0] == searched), None)
        asn_lvl['within'] = {
            'parent': country,
            'share_of_parent': (100.0 * asn_in[1] / country_lvl['total']) if asn_in and country_lvl['total'] else 0.0,
            'rank': int(asn_in[2]) if asn_in else None,
            'of': len(asns_in_country),
        }
        ip_lvl['within'] = {
            'parent': f'{asn} in {country}',
            'share_of_parent': (100.0 * ip_in[1] / sum(r[1] for r in ips_in_slice)) if ip_in and ips_in_slice else 0.0,
            'rank': int(ip_in[2]) if ip_in else None,
            'of': len(ips_in_slice),
        }

        ip_rank = {r[0]: r for r in all_ips}
        selected = []
        for ip in ips:
            r = ip_rank.get(ip)
            c, a = ip_home.get(ip, (None, None))
            selected.append({
                'ip': ip,
                'searched': ip == searched,
                'total': int(r[1]) if r else 0,
                'share': (100.0 * r[1] / grand) if r and grand else 0.0,
                'rank': int(r[2]) if r else None,
                'country': c,
                'asn_name': a,
                'in_top10': bool(r and r[2] <= TOP_N),
            })

        return jsonify({
            'start': start,
            'end': end,
            'top_n': TOP_N,
            'total_attacks': int(grand),
            'searched': searched,
            'levels': {'country': country_lvl, 'asn': asn_lvl, 'ip': ip_lvl},
            'selected_ips': selected,
            'selected_in_top10': sum(1 for s in selected if s['in_top10']),
        })
