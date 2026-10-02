"""
IP Attacks Endpoint
Chart 4: Top IPs with filter support

Every filter is optional and they all combine with AND - see utils/filters.py.
"""

from flask import jsonify, request
from utils.db import get_db, parse_date_params
from utils.filters import sql_str, conditions_sql, source_table, date_range_cte

def register_ip_attacks(app):
    """Register IP attacks endpoint"""

    @app.route('/api/ip_attacks', methods=['GET'])
    def get_ip_attacks():
        """Chart 4: Top IPs, filtered by any combination of country/ASN/IP/username"""
        start, end = parse_date_params()
        args = request.args
        ip_filter = args.get('ip')
        country_filter = args.get('country')

        table = source_table(args)
        cond_sql = conditions_sql(args, 't')

        if ip_filter:
            # Drilled down to one IP: a single series covering every day in range
            query = f"""
                WITH {date_range_cte(start, end)}
                SELECT
                    d.date::VARCHAR AS date,
                    {sql_str(ip_filter)} AS IP,
                    COALESCE(MAX(t.country), 'Unknown') AS country,
                    COALESCE(SUM(t.attacks), 0) AS attacks
                FROM date_range d
                LEFT JOIN {table} t ON d.date = t.date{cond_sql}
                GROUP BY d.date
                ORDER BY d.date
            """
        else:
            # Top 10 IPs that match every filter. When `ips` is set, the IP IN (...)
            # condition limits this to the discovery selection.
            default_country = country_filter if country_filter else 'Mixed'
            query = f"""
                WITH top_ips AS (
                    SELECT t.IP
                    FROM {table} t
                    WHERE t.date BETWEEN '{start}' AND '{end}'{cond_sql}
                    GROUP BY t.IP
                    ORDER BY SUM(t.attacks) DESC
                    LIMIT 10
                ),
                {date_range_cte(start, end)},
                complete_grid AS (
                    SELECT d.date, ti.IP FROM date_range d CROSS JOIN top_ips ti
                )
                SELECT
                    g.date::VARCHAR AS date,
                    g.IP,
                    COALESCE(MAX(t.country), {sql_str(default_country)}) AS country,
                    COALESCE(SUM(t.attacks), 0) AS attacks
                FROM complete_grid g
                LEFT JOIN {table} t
                    ON g.date = t.date AND g.IP = t.IP{cond_sql}
                GROUP BY g.date, g.IP
                ORDER BY g.date, attacks DESC
            """

        conn = get_db()
        result = conn.execute(query).fetchall()
        conn.close()

        data = [{'date': row[0], 'IP': row[1], 'country': row[2], 'attacks': row[3]} for row in result]
        return jsonify(data)