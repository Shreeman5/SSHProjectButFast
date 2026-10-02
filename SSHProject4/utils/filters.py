"""
Shared filter helpers for the chart endpoints.

Every filter is optional and they all combine with AND:
    country / countries   (countries is comma-separated, from discovery)
    asn / asns            (asns is |||-separated, from discovery)
    ip / ips              (ips is |||-separated, from discovery)
    username / usernames  (usernames is |||-separated, from discovery)

A single-value filter (e.g. ip) wins over its list version (e.g. ips), matching
the dashboard's "drill down to one, restore back to the discovery list" behavior.
"""

LIST_SEP = '|||'

IP_TABLE = 'daily_ip_attacks'                    # date, IP, country, asn_name, attacks
IP_USERNAME_TABLE = 'daily_ip_username_attacks'  # same + username


def sql_str(value):
    """Quote a value as a SQL string literal, escaping embedded single quotes."""
    return "'" + str(value).replace("'", "''") + "'"


def _sql_list(raw, sep, strip=True):
    items = raw.split(sep)
    if strip:
        items = [i.strip() for i in items]
    return ', '.join(sql_str(i) for i in items if i != '')


def _add_filter(conditions, column, single, multi, sep, strip=True):
    if single:
        conditions.append(f"{column} = {sql_str(single)}")
    elif multi:
        values = _sql_list(multi, sep, strip)
        if values:
            conditions.append(f"{column} IN ({values})")


def build_conditions(args, alias):
    """Every filter in the request as SQL conditions on table alias `alias`."""
    conditions = []
    _add_filter(conditions, f"{alias}.country", args.get('country'), args.get('countries'), ',')
    _add_filter(conditions, f"{alias}.asn_name", args.get('asn'), args.get('asns'), LIST_SEP)
    _add_filter(conditions, f"{alias}.IP", args.get('ip'), args.get('ips'), LIST_SEP)
    # Usernames are not stripped: leading/trailing spaces can be part of a real SSH username
    _add_filter(conditions, f"{alias}.username", args.get('username'), args.get('usernames'),
                LIST_SEP, strip=False)
    return conditions


def conditions_sql(args, alias):
    """Conditions as a string to append after an existing WHERE/ON clause ('' if none)."""
    return ''.join(f" AND {c}" for c in build_conditions(args, alias))


def has_discovery_selection(args):
    """True when the dashboard is in ASN, IP or username discovery mode.
    (Country discovery mode still uses each endpoint's original summary-table code.)"""
    return bool(args.get('asns') or args.get('ips') or args.get('usernames'))


def source_table(args):
    """Username data only exists in the per-username table; otherwise use the smaller per-IP table."""
    if args.get('username') or args.get('usernames'):
        return IP_USERNAME_TABLE
    return IP_TABLE


def date_range_cte(start, end):
    return f"""date_range AS (
                SELECT UNNEST(generate_series(DATE '{start}', DATE '{end}', INTERVAL 1 DAY))::DATE AS date
            )"""


def total_series_query(table, cond_sql, start, end):
    """One row per day: (date, attacks), zero-filled."""
    return f"""
        WITH {date_range_cte(start, end)}
        SELECT d.date::VARCHAR AS date, COALESCE(SUM(t.attacks), 0) AS attacks
        FROM date_range d
        LEFT JOIN {table} t ON d.date = t.date{cond_sql}
        GROUP BY d.date
        ORDER BY d.date
    """


def top_n_series_query(table, column, cond_sql, start, end, n=10):
    """Top `n` values of `column` matching the filters, one row per (date, value):
    (date, value, attacks), zero-filled."""
    return f"""
        WITH top_values AS (
            SELECT t.{column} AS value
            FROM {table} t
            WHERE t.date BETWEEN '{start}' AND '{end}'{cond_sql}
            GROUP BY t.{column}
            ORDER BY SUM(t.attacks) DESC
            LIMIT {n}
        ),
        {date_range_cte(start, end)},
        complete_grid AS (
            SELECT d.date, tv.value FROM date_range d CROSS JOIN top_values tv
        )
        SELECT g.date::VARCHAR AS date, g.value, COALESCE(SUM(t.attacks), 0) AS attacks
        FROM complete_grid g
        LEFT JOIN {table} t ON g.date = t.date AND g.value = t.{column}{cond_sql}
        GROUP BY g.date, g.value
        ORDER BY g.date, attacks DESC
    """