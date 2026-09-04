"""
Tagging Endpoints  (R4)

A named tag repository plus per-entity tag applications, shared across all
operators. Register in app.py:

    from endpoints.tags_endpoint import register_tags
    register_tags(app)

--------------------------------------------------------------------------------
WHY A SEPARATE DATABASE FILE
--------------------------------------------------------------------------------
Tags live in ./tags.db, NOT in attack_data.db. Three reasons:

1. attack_data.db is derived data. Every table in it can be rebuilt by rerunning
   the scripts in summary_tables_code/, and several of those scripts begin with
   DROP TABLE. Operator-authored tags are the only non-regenerable data in this
   system, so they must not sit next to something that gets dropped and rebuilt.

2. DuckDB permits many read-only connections OR one read-write connection to a
   file, and they are per-process. If utils.db.get_db() opens attack_data.db
   read-only anywhere, a write there would fail. Tags need writes; the attack
   data never does.

3. Backing up tags becomes `cp tags.db tags.db.bak`.

--------------------------------------------------------------------------------
CONCURRENCY
--------------------------------------------------------------------------------
DuckDB allows a single writer. Connections here are opened per request and
closed immediately, so brief overlapping writes retry rather than fail. This is
adequate for a handful of operators on one host; it is not a multi-tenant
design, and that is worth stating as a limitation.
--------------------------------------------------------------------------------
"""

from flask import jsonify, request
import duckdb
import os
import re
import time
from datetime import datetime

TAGS_DB = './tags.db'

VALID_DIMENSIONS = {'username', 'ip', 'asn', 'country'}

# Tag names go into URLs and into the DOM. Keep them boring.
TAG_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 _-]{0,48}$')
HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

DEFAULT_COLOR = '#6c757d'


def _connect(write=False, retries=5):
    """
    Open tags.db. Retries briefly on a write lock rather than 500-ing, since
    two operators tagging at the same moment is the expected case, not an error.
    """
    last = None
    for attempt in range(retries):
        try:
            return duckdb.connect(TAGS_DB, read_only=not write)
        except Exception as e:
            last = e
            time.sleep(0.15 * (attempt + 1))
    raise last


def _init_db():
    """Create the schema once, at registration time."""
    fresh = not os.path.exists(TAGS_DB)
    conn = duckdb.connect(TAGS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            tag_name    VARCHAR PRIMARY KEY,
            color       VARCHAR,
            description VARCHAR,
            created_by  VARCHAR,
            created_at  TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entity_tags (
            dimension  VARCHAR,
            entity_id  VARCHAR,
            tag_name   VARCHAR,
            note       VARCHAR,
            tagged_by  VARCHAR,
            tagged_at  TIMESTAMP,
            PRIMARY KEY (dimension, entity_id, tag_name)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_tags_dim ON entity_tags(dimension)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entity_tags_tag ON entity_tags(tag_name)")
    conn.close()
    if fresh:
        print(f"[TAGS] created {TAGS_DB}")


def _operator(payload=None):
    """
    Who did this. There is no auth in this system, so the client supplies a
    name. Recorded as claimed, not verified -- fine for a research prototype,
    but it is an honest limitation rather than an access control mechanism.
    """
    if payload and payload.get('operator'):
        return str(payload['operator'])[:64]
    return str(request.args.get('operator') or 'unknown')[:64]


def register_tags(app):
    _init_db()

    # =====================================================================
    # Tag repository
    # =====================================================================
    @app.route('/api/tags', methods=['GET'])
    def list_tags():
        """Every tag, with how many entities carry it."""
        dimension = request.args.get('dimension')
        conn = _connect()
        try:
            if dimension:
                if dimension not in VALID_DIMENSIONS:
                    return jsonify({'error': f'Unknown dimension "{dimension}"'}), 400
                rows = conn.execute("""
                    SELECT t.tag_name, t.color, t.description, t.created_by,
                           t.created_at::VARCHAR,
                           COUNT(e.entity_id) FILTER (WHERE e.dimension = ?) AS uses_here,
                           (SELECT COUNT(*) FROM entity_tags x WHERE x.tag_name = t.tag_name) AS uses_total
                    FROM tags t
                    LEFT JOIN entity_tags e ON t.tag_name = e.tag_name
                    GROUP BY 1,2,3,4,5
                    ORDER BY uses_here DESC, t.tag_name
                """, [dimension]).fetchall()
            else:
                rows = conn.execute("""
                    SELECT t.tag_name, t.color, t.description, t.created_by,
                           t.created_at::VARCHAR,
                           COUNT(e.entity_id) AS uses_here,
                           COUNT(e.entity_id) AS uses_total
                    FROM tags t
                    LEFT JOIN entity_tags e ON t.tag_name = e.tag_name
                    GROUP BY 1,2,3,4,5
                    ORDER BY uses_here DESC, t.tag_name
                """).fetchall()
        finally:
            conn.close()

        return jsonify([{
            'tag_name': r[0], 'color': r[1], 'description': r[2],
            'created_by': r[3], 'created_at': r[4],
            'uses_here': r[5], 'uses_total': r[6],
        } for r in rows])

    @app.route('/api/tags', methods=['POST'])
    def create_tag():
        """Create a named tag. Names are unique across all dimensions."""
        body = request.get_json(silent=True) or {}
        name = (body.get('tag_name') or '').strip()
        color = (body.get('color') or DEFAULT_COLOR).strip()
        desc = (body.get('description') or '').strip()

        if not TAG_NAME_RE.match(name):
            return jsonify({'error':
                'Tag name must be 1-49 characters, start with a letter or digit, '
                'and contain only letters, digits, spaces, hyphens or underscores.'}), 400
        if not HEX_COLOR_RE.match(color):
            color = DEFAULT_COLOR

        conn = _connect(write=True)
        try:
            if conn.execute("SELECT 1 FROM tags WHERE tag_name = ?", [name]).fetchone():
                return jsonify({'error': f'Tag "{name}" already exists'}), 409
            conn.execute("INSERT INTO tags VALUES (?, ?, ?, ?, ?)",
                         [name, color, desc, _operator(body), datetime.now()])
        finally:
            conn.close()

        return jsonify({'tag_name': name, 'color': color, 'description': desc,
                        'created_by': _operator(body), 'uses_here': 0, 'uses_total': 0}), 201

    @app.route('/api/tags/<path:tag_name>', methods=['PATCH'])
    def update_tag(tag_name):
        """Change a tag's colour or description. Names are immutable."""
        body = request.get_json(silent=True) or {}
        conn = _connect(write=True)
        try:
            if not conn.execute("SELECT 1 FROM tags WHERE tag_name = ?", [tag_name]).fetchone():
                return jsonify({'error': f'Tag "{tag_name}" not found'}), 404
            if 'color' in body and HEX_COLOR_RE.match(str(body['color'])):
                conn.execute("UPDATE tags SET color = ? WHERE tag_name = ?",
                             [body['color'], tag_name])
            if 'description' in body:
                conn.execute("UPDATE tags SET description = ? WHERE tag_name = ?",
                             [str(body['description'])[:500], tag_name])
        finally:
            conn.close()
        return jsonify({'ok': True, 'tag_name': tag_name})

    @app.route('/api/tags/<path:tag_name>', methods=['DELETE'])
    def delete_tag(tag_name):
        """
        Delete a tag and every application of it.

        FAILSAFE: without ?confirm=true this performs a dry run and reports what
        WOULD be removed. Deleting a tag that 400 usernames carry should never be
        a single unguarded click.
        """
        confirm = request.args.get('confirm') == 'true'
        conn = _connect(write=confirm)
        try:
            if not conn.execute("SELECT 1 FROM tags WHERE tag_name = ?", [tag_name]).fetchone():
                return jsonify({'error': f'Tag "{tag_name}" not found'}), 404

            affected = conn.execute("""
                SELECT dimension, COUNT(*) FROM entity_tags
                WHERE tag_name = ? GROUP BY dimension
            """, [tag_name]).fetchall()
            total = sum(a[1] for a in affected)

            if not confirm:
                return jsonify({
                    'dry_run': True,
                    'tag_name': tag_name,
                    'would_remove': total,
                    'by_dimension': {a[0]: a[1] for a in affected},
                    'detail': f'Deleting "{tag_name}" would also remove it from '
                              f'{total} entit{"y" if total == 1 else "ies"}. '
                              f'Repeat with ?confirm=true to proceed.'
                })

            conn.execute("DELETE FROM entity_tags WHERE tag_name = ?", [tag_name])
            conn.execute("DELETE FROM tags WHERE tag_name = ?", [tag_name])
        finally:
            conn.close()

        return jsonify({'ok': True, 'tag_name': tag_name, 'removed_applications': total})

    # =====================================================================
    # Applying tags to entities
    # =====================================================================
    @app.route('/api/entity_tags/lookup', methods=['POST'])
    def lookup_entity_tags():
        """
        Tags for a specific list of entities.

        POST rather than GET: usernames come out of attack logs and can contain
        slashes, question marks and control characters, none of which survive a
        query string reliably.
        """
        body = request.get_json(silent=True) or {}
        dimension = body.get('dimension')
        entities = body.get('entities') or []

        if dimension not in VALID_DIMENSIONS:
            return jsonify({'error': f'Unknown dimension "{dimension}"'}), 400
        if not isinstance(entities, list):
            return jsonify({'error': 'entities must be a list'}), 400
        if not entities:
            return jsonify({})

        entities = [str(e) for e in entities[:500]]
        ph = ', '.join(['?'] * len(entities))

        conn = _connect()
        try:
            rows = conn.execute(f"""
                SELECT e.entity_id, e.tag_name, e.note, e.tagged_by,
                       e.tagged_at::VARCHAR, COALESCE(t.color, '{DEFAULT_COLOR}')
                FROM entity_tags e
                LEFT JOIN tags t ON e.tag_name = t.tag_name
                WHERE e.dimension = ? AND e.entity_id IN ({ph})
                ORDER BY e.tagged_at
            """, [dimension] + entities).fetchall()
        finally:
            conn.close()

        out = {}
        for r in rows:
            out.setdefault(r[0], []).append({
                'tag_name': r[1], 'note': r[2], 'tagged_by': r[3],
                'tagged_at': r[4], 'color': r[5],
            })
        return jsonify(out)

    @app.route('/api/entity_tags/list', methods=['GET'])
    def list_tagged_entities():
        """Everything tagged in one dimension, newest first."""
        dimension = request.args.get('dimension')
        tag_name = request.args.get('tag_name')
        if dimension not in VALID_DIMENSIONS:
            return jsonify({'error': f'Unknown dimension "{dimension}"'}), 400

        sql = """
            SELECT e.entity_id, e.tag_name, e.note, e.tagged_by,
                   e.tagged_at::VARCHAR, COALESCE(t.color, ?)
            FROM entity_tags e
            LEFT JOIN tags t ON e.tag_name = t.tag_name
            WHERE e.dimension = ?
        """
        params = [DEFAULT_COLOR, dimension]
        if tag_name:
            sql += " AND e.tag_name = ?"
            params.append(tag_name)
        sql += " ORDER BY e.tagged_at DESC LIMIT 1000"

        conn = _connect()
        try:
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()

        return jsonify([{
            'entity_id': r[0], 'tag_name': r[1], 'note': r[2],
            'tagged_by': r[3], 'tagged_at': r[4], 'color': r[5],
        } for r in rows])

    @app.route('/api/entity_tags', methods=['POST'])
    def apply_entity_tags():
        """
        Apply one tag to one or many entities.

        Bulk is the primary path: an operator who has just run a similarity
        search is looking at twenty related usernames and wants to tag the
        campaign, not click twenty times.
        """
        body = request.get_json(silent=True) or {}
        dimension = body.get('dimension')
        entities = body.get('entities') or []
        tag_name = (body.get('tag_name') or '').strip()
        note = (body.get('note') or '').strip()[:500]
        operator = _operator(body)

        if dimension not in VALID_DIMENSIONS:
            return jsonify({'error': f'Unknown dimension "{dimension}"'}), 400
        if not entities:
            return jsonify({'error': 'No entities given'}), 400
        if not tag_name:
            return jsonify({'error': 'No tag_name given'}), 400

        entities = [str(e) for e in entities[:500]]
        now = datetime.now()

        conn = _connect(write=True)
        try:
            if not conn.execute("SELECT 1 FROM tags WHERE tag_name = ?", [tag_name]).fetchone():
                return jsonify({
                    'error': f'Tag "{tag_name}" does not exist. Create it first.',
                    'reason': 'unknown_tag'
                }), 404

            ph = ', '.join(['?'] * len(entities))
            already = {r[0] for r in conn.execute(f"""
                SELECT entity_id FROM entity_tags
                WHERE dimension = ? AND tag_name = ? AND entity_id IN ({ph})
            """, [dimension, tag_name] + entities).fetchall()}

            new = [e for e in entities if e not in already]
            if new:
                conn.executemany(
                    "INSERT INTO entity_tags VALUES (?, ?, ?, ?, ?, ?)",
                    [[dimension, e, tag_name, note, operator, now] for e in new]
                )
        finally:
            conn.close()

        return jsonify({
            'ok': True, 'tag_name': tag_name,
            'applied': len(new), 'already_tagged': len(already),
            'entities': new,
        })

    @app.route('/api/entity_tags/remove', methods=['POST'])
    def remove_entity_tags():
        """
        FAILSAFE: remove a tag from specific entities without deleting the tag
        itself. This is the undo for a bulk apply that selected too much.
        """
        body = request.get_json(silent=True) or {}
        dimension = body.get('dimension')
        entities = body.get('entities') or []
        tag_name = (body.get('tag_name') or '').strip()

        if dimension not in VALID_DIMENSIONS:
            return jsonify({'error': f'Unknown dimension "{dimension}"'}), 400
        if not entities or not tag_name:
            return jsonify({'error': 'entities and tag_name are both required'}), 400

        entities = [str(e) for e in entities[:500]]
        ph = ', '.join(['?'] * len(entities))

        conn = _connect(write=True)
        try:
            before = conn.execute(f"""
                SELECT COUNT(*) FROM entity_tags
                WHERE dimension = ? AND tag_name = ? AND entity_id IN ({ph})
            """, [dimension, tag_name] + entities).fetchone()[0]

            conn.execute(f"""
                DELETE FROM entity_tags
                WHERE dimension = ? AND tag_name = ? AND entity_id IN ({ph})
            """, [dimension, tag_name] + entities)
        finally:
            conn.close()

        return jsonify({'ok': True, 'removed': before, 'tag_name': tag_name})

    @app.route('/api/tags/stats', methods=['GET'])
    def tag_stats():
        """Small summary for the manager panel header."""
        conn = _connect()
        try:
            n_tags = conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
            n_apps = conn.execute("SELECT COUNT(*) FROM entity_tags").fetchone()[0]
            by_dim = conn.execute("""
                SELECT dimension, COUNT(*), COUNT(DISTINCT entity_id)
                FROM entity_tags GROUP BY dimension
            """).fetchall()
            ops = conn.execute("""
                SELECT tagged_by, COUNT(*) FROM entity_tags
                GROUP BY tagged_by ORDER BY 2 DESC LIMIT 10
            """).fetchall()
        finally:
            conn.close()

        return jsonify({
            'total_tags': n_tags,
            'total_applications': n_apps,
            'by_dimension': {r[0]: {'applications': r[1], 'entities': r[2]} for r in by_dim},
            'by_operator': {r[0]: r[1] for r in ops},
            'database': TAGS_DB,
        })