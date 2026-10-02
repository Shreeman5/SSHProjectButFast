"""
Username-overlap similarity between IPs.

Cosine similarity of TF-IDF weighted username vectors (see
summary_tables_code/create_ip_username_vectors.py for how the vectors are
built and why). Scores are returned as percentages, 0-100.

Independent of the behavioural clustering: two IPs can be behavioural
strangers (different cluster, ASN and country) and still score high here if
they try the same unusual usernames.

RARE USERNAMES
--------------
Cosine measures the direction of two vectors, not their size, so two IPs whose
lists contain ONLY common usernames (root, admin, test...) can score near 100%
while sharing nothing distinctive. Two safeguards:

  * Every result reports `distinctive_shared_count`: how many of the shared
    usernames are rare, i.e. tried by fewer than DISTINCTIVE_MAX_SHARE of all IPs.
  * The all-IP search can require at least one rare shared username
    (`require_distinctive`, on by default), which drops common-only matches.

"Tried by fewer than 1% of IPs" is the same as idf > ln(1 / 0.01), so the test
reads the existing username_idf table; nothing needs rebuilding.
"""

import math

TOP_SHARED = 10  # usernames listed per result (the full counts are shared_username_count / distinctive_shared_count)

# A username is "rare" (distinctive) if fewer than this share of IPs tried it.
DISTINCTIVE_MAX_SHARE = 0.01
DISTINCTIVE_MIN_IDF = math.log(1 / DISTINCTIVE_MAX_SHARE)   # idf = ln(N / ip_count)

REQUIRED_TABLES = ('ip_username_tfidf', 'ip_username_norm', 'username_idf')

NOT_READY_MESSAGE = ('Username similarity tables are missing. Stop Flask, run '
                     'python summary_tables_code/create_ip_username_vectors.py, then restart.')


def tables_ready(conn):
    names = {r[0] for r in conn.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    return all(t in names for t in REQUIRED_TABLES)


def target_profile(conn, ip):
    """(norm, n_usernames) for an IP, or None if it has no weighted usernames
    (no username data, or only usernames that every IP tries)."""
    return conn.execute(
        "SELECT norm, n_usernames FROM ip_username_norm WHERE ip = ?", [ip]
    ).fetchone()


def distinctive_count(conn, ip):
    """How many rare usernames an IP tried."""
    return conn.execute("""
        SELECT COUNT(*)
        FROM ip_username_tfidf w JOIN username_idf i ON w.username = i.username
        WHERE w.ip = ? AND i.idf > ?
    """, [ip, DISTINCTIVE_MIN_IDF]).fetchone()[0]


def own_usernames(conn, ip, n=TOP_SHARED):
    """An IP's own heaviest usernames, for showing the searched IP itself.

    Returns {'top_usernames': [...], 'rare_usernames': [...]} -- up to n of each,
    ordered by weight (the same weight that drives the similarity score).
    """
    rows = conn.execute("""
        SELECT w.username, i.idf
        FROM ip_username_tfidf w JOIN username_idf i ON w.username = i.username
        WHERE w.ip = ?
        ORDER BY w.weight DESC, w.username
    """, [ip]).fetchall()
    return {
        'top_usernames': [u for u, _ in rows[:n]],
        'rare_usernames': [u for u, idf in rows if idf > DISTINCTIVE_MIN_IDF][:n],
    }


def similarity_to(conn, target_ip, candidate_ips):
    """Username similarity of each candidate to the target.

    Returns {ip: {'username_similarity': pct, 'shared_username_count': n,
                  'distinctive_shared_count': n_rare,
                  'shared_usernames': [top usernames by contribution],
                  'rare_shared_usernames': [top rare ones by contribution]}}.
    Candidates that share no weighted username get 0 and an empty list.
    """
    out = {ip: {'username_similarity': 0.0, 'shared_username_count': 0,
                'distinctive_shared_count': 0, 'shared_usernames': [],
                'rare_shared_usernames': []}
           for ip in candidate_ips}
    if not candidate_ips:
        return out

    t = target_profile(conn, target_ip)
    if not t or not t[0]:
        return out
    t_norm = float(t[0])

    ph = ', '.join(['?'] * len(candidate_ips))
    rare_idf = repr(float(DISTINCTIVE_MIN_IDF))
    rows = conn.execute(f"""
        WITH t AS (
            SELECT w.username, w.weight, i.idf
            FROM ip_username_tfidf w JOIN username_idf i ON w.username = i.username
            WHERE w.ip = ?
        ),
        contrib AS (
            SELECT v.ip, v.username, v.weight * t.weight AS c, t.idf
            FROM ip_username_tfidf v
            JOIN t ON v.username = t.username
            WHERE v.ip IN ({ph})
        ),
        ranked AS (
            SELECT ip, username, c, idf,
                   ROW_NUMBER() OVER (PARTITION BY ip ORDER BY c DESC, username) AS rn,
                   -- numbering within rare / not-rare, so the top rare ones can be listed too
                   ROW_NUMBER() OVER (PARTITION BY ip, idf > {rare_idf} ORDER BY c DESC, username) AS rn_split
            FROM contrib
        )
        SELECT r.ip,
               SUM(r.c) AS dot,
               COUNT(*) AS shared,
               COUNT(*) FILTER (WHERE r.idf > {rare_idf}) AS distinctive,
               LIST(r.username ORDER BY r.rn) FILTER (WHERE r.rn <= {TOP_SHARED}) AS top_shared,
               LIST(r.username ORDER BY r.rn_split)
                   FILTER (WHERE r.idf > {rare_idf} AND r.rn_split <= {TOP_SHARED}) AS rare_shared,
               ANY_VALUE(n.norm) AS norm
        FROM ranked r
        JOIN ip_username_norm n ON n.ip = r.ip
        GROUP BY r.ip
    """, [target_ip, *candidate_ips]).fetchall()

    for ip, dot, shared, distinctive, top_shared, rare_shared, norm in rows:
        cos = float(dot) / (t_norm * float(norm)) if norm else 0.0
        out[ip] = {
            'username_similarity': round(min(cos, 1.0) * 100, 1),
            'shared_username_count': int(shared),
            'distinctive_shared_count': int(distinctive),
            'shared_usernames': list(top_shared or []),
            'rare_shared_usernames': list(rare_shared or []),
        }
    return out


def search(conn, target_ip, limit, require_distinctive=True):
    """Top `limit` IPs across ALL IPs by username similarity to the target.

    With require_distinctive, an IP only qualifies if it shares at least one
    rare username with the target (see RARE USERNAMES above).

    Returns [(ip, username_similarity_pct, n_usernames)] best first, or None if
    the target has no weighted usernames.
    """
    t = target_profile(conn, target_ip)
    if not t or not t[0]:
        return None

    rows = conn.execute("""
        WITH t AS (
            SELECT w.username, w.weight, i.idf
            FROM ip_username_tfidf w JOIN username_idf i ON w.username = i.username
            WHERE w.ip = ?
        ),
        s AS (
            SELECT v.ip,
                   SUM(v.weight * t.weight) AS dot,
                   COUNT(*) FILTER (WHERE t.idf > ?) AS distinctive
            FROM ip_username_tfidf v
            JOIN t ON v.username = t.username
            WHERE v.ip != ?
            GROUP BY v.ip
        )
        SELECT s.ip, s.dot / (n.norm * ?) AS cos, n.n_usernames
        FROM s JOIN ip_username_norm n ON n.ip = s.ip
        WHERE s.distinctive >= ?
        ORDER BY cos DESC, s.ip
        LIMIT ?
    """, [target_ip, DISTINCTIVE_MIN_IDF, target_ip, float(t[0]),
          1 if require_distinctive else 0, limit]).fetchall()

    return [(ip, round(min(float(cos), 1.0) * 100, 1), n) for ip, cos, n in rows]