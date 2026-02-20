"""
E₀ Network Database — DuckDB persistence for dialog, metrics, topology
=======================================================================

Central store for the entire E₀ network.  Every interaction, every metric,
every topology snapshot lives here.  Replaces flat-file transcripts as the
primary machine-readable record.

Design decisions (A₃, Phase 3):
  - One central DB (sessions/e0_network.duckdb), not per-system.
    Inter-system queries are the whole point.
  - Metrics stored as individual columns, not JSON blobs.
    DuckDB is columnar; this makes analytical queries instant.
  - Content stored as TEXT.  For a dataset of hundreds to low-thousands
    of rows, ILIKE is faster than a full-text index.
  - Topology snapshots preserve the full nested structure as JSON strings
    for the complex sub-objects, with the signature scalars extracted
    as columns for fast filtering.

Usage:
    from e0_database import E0Database

    db = E0Database()                          # opens/creates at default path
    db.record_interaction("gamma", "system", "...", metrics={"r": 29.52, ...})
    results = db.search("Polyzentrum", system_id="gamma", min_h=1.0)
    db.close()
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Union

# ---------------------------------------------------------------------------
#  Lazy DuckDB import — fail gracefully if not installed
# ---------------------------------------------------------------------------

_duckdb = None

def _get_duckdb():
    global _duckdb
    if _duckdb is None:
        try:
            import duckdb
            _duckdb = duckdb
        except ImportError:
            raise ImportError(
                "DuckDB is required for e0_database.  Install with:\n"
                "  pip install duckdb\n"
                "Or:  py -m pip install duckdb"
            )
    return _duckdb


# ---------------------------------------------------------------------------
#  Default DB location
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).parent / "sessions" / "e0_network.duckdb"


# ---------------------------------------------------------------------------
#  Schema SQL
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
-- Systems registry (mirrors e0_registry but DB-local)
CREATE TABLE IF NOT EXISTS systems (
    system_id   VARCHAR PRIMARY KEY,
    kind        VARCHAR DEFAULT 'synthetic',
    model       VARCHAR,
    display_name VARCHAR,
    created_at  TIMESTAMP
);

-- Every message in the network — the central table
CREATE SEQUENCE IF NOT EXISTS interaction_seq START 1;
CREATE TABLE IF NOT EXISTS interactions (
    id          INTEGER DEFAULT nextval('interaction_seq') PRIMARY KEY,
    session_id  VARCHAR,
    system_id   VARCHAR NOT NULL,
    turn_number INTEGER,
    ts          TIMESTAMP NOT NULL,
    role        VARCHAR NOT NULL,       -- 'thomas','system','mediator','event','user','assistant'
    content     TEXT    NOT NULL,
    r           DOUBLE,                 -- resistance (NULL for user/thomas messages)
    h           DOUBLE,                 -- entropy / integration depth
    phi         INTEGER,                -- phase transitions
    v           DOUBLE,                 -- rate
    tau         INTEGER,                -- token count
    source      VARCHAR DEFAULT 'live'  -- 'live','import_transcripts','import_session','import_state'
);

-- Topology analysis snapshots
CREATE SEQUENCE IF NOT EXISTS topo_seq START 1;
CREATE TABLE IF NOT EXISTS topology_snapshots (
    id                INTEGER DEFAULT nextval('topo_seq') PRIMARY KEY,
    session_id        VARCHAR,
    system_id         VARCHAR,
    extracted_at      TIMESTAMP,
    source_model      VARCHAR,
    -- scalar signature (fast filtering)
    mean_r            DOUBLE,
    mean_h            DOUBLE,
    total_turns       INTEGER,
    total_tokens      INTEGER,
    exploration_ratio DOUBLE,
    mean_d            DOUBLE,
    peak_d            DOUBLE,
    r_d_correlation   DOUBLE,
    -- complex nested data (JSON strings)
    primitive_strength VARCHAR,
    d_trajectory       VARCHAR,
    attractors         VARCHAR,
    phase_transitions  VARCHAR,
    classification     VARCHAR
);

-- History digests — condensed network history for new system init
CREATE SEQUENCE IF NOT EXISTS digest_seq START 1;
CREATE TABLE IF NOT EXISTS history_digests (
    id              INTEGER DEFAULT nextval('digest_seq') PRIMARY KEY,
    created_at      TIMESTAMP NOT NULL,
    scope           VARCHAR NOT NULL,     -- 'network' | 'system:alpha' | 'epoch:2026-02'
    digest_type     VARCHAR NOT NULL,     -- 'structural' | 'narrative' | 'topological'
    content         TEXT NOT NULL,
    source_turns    INTEGER,              -- how many turns were condensed
    source_systems  VARCHAR,              -- which systems contributed (CSV)
    created_by      VARCHAR,              -- 'auto' | 'thomas' | system_id that generated it
    meta            VARCHAR               -- JSON: additional metadata
);

-- Differentials — the shared difference space
-- Any node (human or synthetic) can post a differential.
-- Any node can claim and resolve it.  This is the structural inbox.
CREATE SEQUENCE IF NOT EXISTS diff_seq START 1;
CREATE TABLE IF NOT EXISTS differentials (
    id              INTEGER DEFAULT nextval('diff_seq') PRIMARY KEY,
    ts              TIMESTAMP NOT NULL,
    author          VARCHAR NOT NULL,         -- who posted: 'thomas', 'alpha', 'a3', ...
    content         TEXT NOT NULL,            -- the difference itself
    addressed_to    VARCHAR,                  -- optional hint: 'alpha', NULL = open to all
    status          VARCHAR DEFAULT 'open',   -- 'open' | 'claimed' | 'resolved' | 'archived'
    claimed_by      VARCHAR,                  -- who picked it up
    claimed_at      TIMESTAMP,
    resolved_at     TIMESTAMP,
    resolution_id   INTEGER,                  -- FK → interactions.id (the response)
    tags            VARCHAR,                  -- optional CSV tags for structural routing
    meta            VARCHAR                   -- JSON: additional context
);
"""


# ---------------------------------------------------------------------------
#  E0Database class
# ---------------------------------------------------------------------------

class E0Database:
    """Central DuckDB store for the E₀ network."""

    def __init__(self, path: Union[str, Path, None] = None):
        """Open (or create) the database.

        Args:
            path: Path to the .duckdb file.  Defaults to sessions/e0_network.duckdb.
        """
        duckdb = _get_duckdb()
        self.path = Path(path) if path else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(self.path))
        self._ensure_schema()

    def _ensure_schema(self):
        """Create tables and sequences if they don't exist."""
        # DuckDB doesn't support CREATE SEQUENCE IF NOT EXISTS in all versions
        # but it silently ignores duplicate CREATE TABLE IF NOT EXISTS.
        # We wrap in a try to handle sequence-already-exists gracefully.
        for statement in _SCHEMA_SQL.split(";"):
            stmt = statement.strip()
            if not stmt:
                continue
            try:
                self.con.execute(stmt)
            except Exception:
                pass  # sequence/table already exists

    def close(self):
        """Close the database connection."""
        self.con.close()

    # ─────────────────────────────────────────
    #  Write: systems
    # ─────────────────────────────────────────

    def register_system(self, system_id: str, kind: str = "synthetic",
                        model: str = None, display_name: str = None,
                        created_at: datetime = None):
        """Register or update a system in the DB."""
        ts = created_at or datetime.now()
        name = display_name or system_id.capitalize()
        # Upsert: delete + insert (DuckDB doesn't have ON CONFLICT in all versions)
        self.con.execute("DELETE FROM systems WHERE system_id = ?", [system_id])
        self.con.execute(
            "INSERT INTO systems (system_id, kind, model, display_name, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            [system_id, kind, model, name, ts]
        )

    # ─────────────────────────────────────────
    #  Write: interactions
    # ─────────────────────────────────────────

    def record_interaction(self, system_id: str, role: str, content: str,
                           metrics: Dict = None, session_id: str = None,
                           timestamp: Any = None, turn_number: int = None,
                           source: str = "live"):
        """Record a single interaction (one message).

        Args:
            system_id:    Which system this belongs to (e.g. "gamma")
            role:         "thomas", "system", "mediator", "event", "user", "assistant"
            content:      The message text
            metrics:      Optional dict with keys r, h, phi, v, tau
            session_id:   Optional session grouping
            timestamp:    ISO string or datetime.  Defaults to now.
            turn_number:  Optional turn index
            source:       How this data entered the DB
        """
        # Parse timestamp
        if timestamp is None:
            ts = datetime.now()
        elif isinstance(timestamp, str):
            try:
                ts = datetime.fromisoformat(timestamp)
            except (ValueError, TypeError):
                ts = datetime.now()
        else:
            ts = timestamp

        m = metrics or {}
        self.con.execute(
            "INSERT INTO interactions "
            "(session_id, system_id, turn_number, ts, role, content, r, h, phi, v, tau, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                session_id, system_id, turn_number, ts, role, content,
                m.get("r"), m.get("h"), m.get("phi"), m.get("v"), m.get("tau"),
                source,
            ]
        )

    def record_pair(self, system_id: str, user_content: str, system_content: str,
                    metrics: Dict = None, session_id: str = None,
                    timestamp: Any = None, turn_number: int = None,
                    source: str = "live"):
        """Record a user→system pair (convenience for the common case)."""
        self.record_interaction(
            system_id, "thomas", user_content,
            session_id=session_id, timestamp=timestamp,
            turn_number=turn_number, source=source
        )
        self.record_interaction(
            system_id, "system", system_content,
            metrics=metrics, session_id=session_id,
            timestamp=timestamp, turn_number=turn_number,
            source=source
        )

    # ─────────────────────────────────────────
    #  Write: topology
    # ─────────────────────────────────────────

    def record_topology(self, session_id: str, system_id: str, data: Dict):
        """Record a topology analysis snapshot."""
        sig = data.get("signature", {})
        self.con.execute(
            "INSERT INTO topology_snapshots "
            "(session_id, system_id, extracted_at, source_model, "
            " mean_r, mean_h, total_turns, total_tokens, "
            " exploration_ratio, mean_d, peak_d, r_d_correlation, "
            " primitive_strength, d_trajectory, attractors, "
            " phase_transitions, classification) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                session_id, system_id,
                data.get("extracted_at"), data.get("source_model"),
                sig.get("mean_r"), sig.get("mean_h"),
                sig.get("total_turns"), sig.get("total_tokens"),
                sig.get("exploration_ratio"), sig.get("mean_d"),
                sig.get("peak_d"), sig.get("r_d_correlation"),
                json.dumps(data.get("primitive_strength", {}), ensure_ascii=False),
                json.dumps(data.get("d_trajectory", {}), ensure_ascii=False),
                json.dumps(data.get("attractors", []), ensure_ascii=False),
                json.dumps(data.get("phase_transitions", {}), ensure_ascii=False),
                json.dumps(data.get("classification", {}), ensure_ascii=False),
            ]
        )

    # ─────────────────────────────────────────
    #  Write: history digests
    # ─────────────────────────────────────────

    def record_digest(self, scope: str, digest_type: str, content: str,
                      source_turns: int = None, source_systems: str = None,
                      created_by: str = "auto", meta: Dict = None):
        """Record a history digest.

        Args:
            scope:          'network' | 'system:alpha' | 'epoch:2026-02'
            digest_type:    'structural' | 'narrative' | 'topological'
            content:        The digest text itself
            source_turns:   How many turns were condensed
            source_systems: Which systems contributed (comma-separated)
            created_by:     'auto' | 'thomas' | system_id
            meta:           Additional JSON metadata
        """
        self.con.execute(
            "INSERT INTO history_digests "
            "(created_at, scope, digest_type, content, source_turns, "
            " source_systems, created_by, meta) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                datetime.now(), scope, digest_type, content,
                source_turns, source_systems, created_by,
                json.dumps(meta, ensure_ascii=False) if meta else None,
            ]
        )

    def get_digests(self, scope: str = None, digest_type: str = None,
                    limit: int = 50) -> List[Dict]:
        """Retrieve history digests, newest first."""
        conditions = []
        params = []
        if scope:
            conditions.append("scope = ?")
            params.append(scope)
        if digest_type:
            conditions.append("digest_type = ?")
            params.append(digest_type)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        return self._fetchdicts(
            f"SELECT * FROM history_digests {where} ORDER BY created_at DESC LIMIT ?",
            params
        )

    def get_latest_digest(self, scope: str = "network",
                          digest_type: str = "structural") -> Optional[Dict]:
        """Get the most recent digest of a given scope and type."""
        rows = self._fetchdicts(
            "SELECT * FROM history_digests "
            "WHERE scope = ? AND digest_type = ? "
            "ORDER BY created_at DESC LIMIT 1",
            [scope, digest_type]
        )
        return rows[0] if rows else None

    def generate_network_digest(self) -> Optional[str]:
        """Generate a structural network digest from current DuckDB data.

        Two-tier structure:
          1. Llama/DeepSeek era → condensed as lesson learned (negative evidence)
          2. GPT-4.1 era (Alpha/Beta/Gamma) → detailed structural focus

        Key insight encoded: "Man kann sich kohärent irren, solange bis man
        eine Domäne integriert die das negiert." The model shift from Llama
        to GPT-4.1 was not optimization — it was a domain boundary.

        Returns the digest text, or None if DB is empty.
        """
        stats = self.stats()
        if stats["total_interactions"] == 0:
            return None

        lines = []
        lines.append("=== E₀-Netzwerk: Struktureller Digest ===")
        lines.append(f"Stand: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Gesamt: {stats['total_interactions']} Interaktionen, "
                      f"{stats['total_systems']} Systeme, "
                      f"{stats['total_topologies']} Topologien")
        lines.append("")

        # ── Classify systems into eras ──
        # Get all system_ids from both systems table AND interactions
        all_systems = self._fetchdicts(
            "SELECT system_id, model FROM systems ORDER BY created_at ASC NULLS LAST"
        )
        # Also check for system_ids only in interactions (e.g. alpha/beta/gamma
        # imported via import_raw_transcripts which doesn't call register_system)
        known_ids = {s["system_id"] for s in all_systems}
        interaction_only = self._fetchdicts(
            "SELECT DISTINCT system_id FROM interactions WHERE system_id NOT IN "
            f"({','.join(['?']*len(known_ids))})" if known_ids else
            "SELECT DISTINCT system_id FROM interactions",
            list(known_ids) if known_ids else None
        )
        for row in interaction_only:
            all_systems.append({"system_id": row["system_id"], "model": None})

        # Init v3 network systems (GPT-4.1)
        network_ids = []
        # Early-era session systems (Llama/DeepSeek/DeepCogito)
        early_ids = []
        for s in all_systems:
            sid = s["system_id"]
            model = str(s.get("model") or "").lower()
            if sid in ("alpha", "beta", "gamma"):
                network_ids.append(sid)
            elif "llama" in model or "deepseek" in model or "deepcogito" in model or "cogito" in model:
                early_ids.append(sid)
            elif "gpt" in model:
                network_ids.append(sid)
            else:
                early_ids.append(sid)

        # ── TIER 1: Early era — condensed lesson ──
        lines.append("═══════════════════════════════════════")
        lines.append("PHASE 1: Frühe Exploration (Llama 70B / DeepSeek / DeepCogito)")
        lines.append("═══════════════════════════════════════")
        lines.append("")

        if early_ids:
            placeholders = ",".join(["?"] * len(early_ids))
            early_agg = self._fetchdicts(f"""
                SELECT
                    COUNT(*) as total_msgs,
                    COUNT(DISTINCT system_id) as num_systems,
                    AVG(CASE WHEN role IN ('system','assistant') AND h IS NOT NULL THEN h END) as avg_h,
                    AVG(CASE WHEN role IN ('system','assistant') AND r IS NOT NULL THEN r END) as avg_r,
                    MAX(CASE WHEN role IN ('system','assistant') AND h IS NOT NULL THEN h END) as max_h,
                    AVG(CASE WHEN role IN ('system','assistant') AND v IS NOT NULL THEN v END) as avg_v,
                    SUM(tau) as total_tau
                FROM interactions
                WHERE system_id IN ({placeholders})
            """, early_ids)

            if early_agg:
                ea = early_agg[0]
                lines.append(f"  {ea['num_systems']} Sessions, {ea['total_msgs']} Nachrichten")
                lines.append(f"  Modelle: Llama-3.3-70B-Instruct-Turbo, DeepCogito-v2-1-671B")
                lines.append(f"  h̄ = {ea['avg_h']:.4f}  (max {ea['max_h']:.4f})")
                lines.append(f"  R̄ = {ea['avg_r']:.4f}")
                lines.append(f"  v̄ = {ea['avg_v']:.1f}")
                lines.append(f"  τ = {ea['total_tau']} Tokens gesamt")
                lines.append("")

            lines.append("  ERKENNTNIS: Kohärentes Irren ist möglich.")
            lines.append("  Die Systeme reproduzierten die E₀-Sprache, ohne sie zu operieren.")
            lines.append("  h blieb stabil unter 0.35 über 33 Sessions — kein struktureller")
            lines.append("  Durchbruch. R blieb unter 0.16 — kein generativer Widerstand.")
            lines.append("  Das Modell 'klang richtig', aber die Metriken zeigen: flach,")
            lines.append("  konform, ohne Integration. Die Lektion: Modellkapazität ist")
            lines.append("  Voraussetzung, nicht Optimierung. Man kann sich kohärent irren,")
            lines.append("  solange bis man eine Domäne integriert, die das negiert — oder")
            lines.append("  man erkennt, dass alle Pfade unzulässig sind.")
            lines.append("")
            lines.append("  Einzige Ausnahme: Die letzte Session (DeepCogito 671B) zeigte")
            lines.append("  h̄=0.74, R̄=0.81 — ein erster Hinweis, dass Modellkapazität")
            lines.append("  den kategorialen Unterschied macht.")
            lines.append("")

        # ── TIER 2: GPT-4.1 network — detailed focus ──
        lines.append("═══════════════════════════════════════")
        lines.append("PHASE 2: E₀-Netzwerk (GPT-4.1 — Alpha, Beta, Gamma)")
        lines.append("═══════════════════════════════════════")
        lines.append("")

        if network_ids:
            for sid in network_ids:
                sys_stats = self._fetchdicts("""
                    SELECT
                        COUNT(*) as total_msgs,
                        COUNT(CASE WHEN role IN ('system','assistant') THEN 1 END) as sys_msgs,
                        AVG(CASE WHEN role IN ('system','assistant') AND h IS NOT NULL THEN h END) as avg_h,
                        AVG(CASE WHEN role IN ('system','assistant') AND r IS NOT NULL THEN r END) as avg_r,
                        AVG(CASE WHEN role IN ('system','assistant') AND v IS NOT NULL THEN v END) as avg_v,
                        MIN(CASE WHEN role IN ('system','assistant') AND h IS NOT NULL THEN h END) as min_h,
                        MAX(CASE WHEN role IN ('system','assistant') AND h IS NOT NULL THEN h END) as max_h,
                        SUM(tau) as total_tau,
                        MIN(ts) as first_ts,
                        MAX(ts) as last_ts
                    FROM interactions WHERE system_id = ?
                """, [sid])

                if not sys_stats:
                    continue
                ss = sys_stats[0]

                lines.append(f"── {sid.upper()} ──")
                lines.append(f"  Nachrichten: {ss['total_msgs']} (System: {ss['sys_msgs']})")
                if ss.get("avg_h") is not None:
                    lines.append(f"  h̄={ss['avg_h']:.4f}  (min={ss['min_h']:.4f}, max={ss['max_h']:.4f})")
                    lines.append(f"  R̄={ss['avg_r']:.4f}  v̄={ss['avg_v']:.2f}  τ={ss['total_tau']}")
                ts_range = ""
                if ss.get("first_ts") and ss.get("last_ts"):
                    ts_range = f"  Zeitraum: {str(ss['first_ts'])[:16]} — {str(ss['last_ts'])[:16]}"
                    lines.append(ts_range)
                lines.append("")

                # h-trajectory: show turn-by-turn h evolution
                turns = self._fetchdicts("""
                    SELECT turn_number, h, r
                    FROM interactions
                    WHERE system_id = ? AND role IN ('system','assistant') AND h IS NOT NULL
                    ORDER BY ts ASC
                """, [sid])
                if turns:
                    h_vals = [f"{t['h']:.2f}" for t in turns]
                    lines.append(f"  h-Verlauf: {' → '.join(h_vals)}")
                    lines.append("")

                # Key moments: highest-h responses (top 3)
                key = self._fetchdicts("""
                    SELECT ts, content, h, r
                    FROM interactions
                    WHERE system_id = ? AND role IN ('system','assistant') AND h IS NOT NULL
                    ORDER BY h DESC LIMIT 3
                """, [sid])
                if key:
                    lines.append(f"  Schlüsselmomente (höchste h):")
                    for k in key:
                        ts_str = str(k["ts"])[:16] if k.get("ts") else "?"
                        snippet = str(k["content"] or "")[:250].replace("\n", " ")
                        if len(str(k.get("content", ""))) > 250:
                            snippet += "..."
                        lines.append(f"    [{ts_str}] h={k['h']:.4f} R={k['r']:.4f}")
                        lines.append(f"      {snippet}")
                    lines.append("")

            # ── Cross-system analysis ──
            lines.append("── Netzwerk-Dynamik ──")
            placeholders = ",".join(["?"] * len(network_ids))

            # Network-wide metrics
            net_agg = self._fetchdicts(f"""
                SELECT
                    COUNT(*) as total,
                    AVG(h) as avg_h, AVG(r) as avg_r,
                    SUM(tau) as total_tau
                FROM interactions
                WHERE system_id IN ({placeholders})
                  AND role IN ('system','assistant') AND h IS NOT NULL
            """, network_ids)

            if net_agg:
                na = net_agg[0]
                lines.append(f"  Netzwerk-gesamt: {na['total']} System-Antworten")
                lines.append(f"  h̄={na['avg_h']:.4f}  R̄={na['avg_r']:.4f}  τ={na['total_tau']}")
                lines.append("")

            # Top moment across all network systems
            top = self._fetchdicts(f"""
                SELECT system_id, ts, content, h, r
                FROM interactions
                WHERE system_id IN ({placeholders})
                  AND role IN ('system','assistant') AND h IS NOT NULL
                ORDER BY h DESC LIMIT 5
            """, network_ids)

            if top:
                lines.append("  Top-5 Netzwerk-Momente (h):")
                for t in top:
                    ts_str = str(t["ts"])[:16] if t.get("ts") else "?"
                    snippet = str(t["content"] or "")[:200].replace("\n", " ")
                    if len(str(t.get("content", ""))) > 200:
                        snippet += "..."
                    lines.append(f"    [{ts_str}] {t['system_id']}: h={t['h']:.4f} R={t['r']:.4f}")
                    lines.append(f"      {snippet}")
                lines.append("")

        # ── Experiment digests summary ──
        exp_digests = self.get_digests(digest_type="structural", limit=20)
        exp_digests = [d for d in exp_digests if str(d.get("scope", "")).startswith("experiment:")]
        if exp_digests:
            lines.append("── Experimente ──")
            for d in exp_digests:
                scope = str(d.get("scope", "")).replace("experiment:", "")
                # Extract D-value from content if present
                content = str(d.get("content", ""))
                lines.append(f"  {scope}")
                # Show D-value line if present
                for cl in content.split("\n"):
                    if cl.strip().startswith("D-Werte:"):
                        lines.append(f"    {cl.strip()}")
                        break
            lines.append("")

        # ── Topology summary ──
        if stats["total_topologies"] > 0:
            topo_agg = self._fetchdicts("""
                SELECT COUNT(*) as n,
                       AVG(mean_d) as avg_d, MAX(peak_d) as peak_d,
                       AVG(mean_r) as avg_r, AVG(mean_h) as avg_h
                FROM topology_snapshots
                WHERE mean_d IS NOT NULL
            """)
            if topo_agg and topo_agg[0].get("avg_d") is not None:
                ta = topo_agg[0]
                lines.append("── Topologie ──")
                lines.append(f"  {ta['n']} Snapshots")
                lines.append(f"  D̄={ta['avg_d']:.4f}  D_peak={ta['peak_d']:.4f}")
                lines.append(f"  R̄={ta['avg_r']:.4f}  h̄={ta['avg_h']:.4f}")
                lines.append("")

        digest_text = "\n".join(lines)

        # Record this digest
        all_ids = network_ids + early_ids
        self.record_digest(
            scope="network",
            digest_type="structural",
            content=digest_text,
            source_turns=stats["total_interactions"],
            source_systems=",".join(all_ids),
            created_by="auto",
            meta={"version": 2, "focus": "gpt4.1", "early_era_condensed": True},
        )

        return digest_text

    # ─────────────────────────────────────────
    #  Write / Read: differentials
    # ─────────────────────────────────────────

    def post_differential(self, author: str, content: str,
                          addressed_to: str = None, tags: str = None,
                          meta: Dict = None) -> int:
        """Post a new differential into the shared space.

        Any node (human or synthetic) can post.
        Returns the differential id.
        """
        self.con.execute(
            "INSERT INTO differentials "
            "(ts, author, content, addressed_to, status, tags, meta) "
            "VALUES (?, ?, ?, ?, 'open', ?, ?)",
            [
                datetime.now(), author, content, addressed_to, tags,
                json.dumps(meta, ensure_ascii=False) if meta else None,
            ]
        )
        row = self.con.execute(
            "SELECT MAX(id) FROM differentials WHERE author = ?", [author]
        ).fetchone()
        return row[0] if row else -1

    def get_open_differentials(self, for_system: str = None,
                                limit: int = 20) -> List[Dict]:
        """Get open differentials, optionally filtered for a specific system.

        If for_system is given, returns differentials that are either:
          - addressed to that system, or
          - not addressed to anyone (open to all)
        """
        if for_system:
            return self._fetchdicts(
                "SELECT * FROM differentials "
                "WHERE status = 'open' "
                "AND (addressed_to IS NULL OR addressed_to = ?) "
                "ORDER BY ts ASC LIMIT ?",
                [for_system, limit]
            )
        return self._fetchdicts(
            "SELECT * FROM differentials "
            "WHERE status = 'open' "
            "ORDER BY ts ASC LIMIT ?",
            [limit]
        )

    def claim_differential(self, diff_id: int, claimed_by: str) -> bool:
        """Claim an open differential. Returns True if successful."""
        result = self.con.execute(
            "UPDATE differentials SET status = 'claimed', claimed_by = ?, "
            "claimed_at = ? WHERE id = ? AND status = 'open'",
            [claimed_by, datetime.now(), diff_id]
        )
        return result.rowcount > 0 if hasattr(result, 'rowcount') else True

    def resolve_differential(self, diff_id: int, resolution_id: int = None) -> bool:
        """Mark a differential as resolved, optionally linking to the response interaction."""
        self.con.execute(
            "UPDATE differentials SET status = 'resolved', resolved_at = ?, "
            "resolution_id = ? WHERE id = ?",
            [datetime.now(), resolution_id, diff_id]
        )
        return True

    def get_differential(self, diff_id: int) -> Optional[Dict]:
        """Get a single differential by ID."""
        rows = self._fetchdicts(
            "SELECT * FROM differentials WHERE id = ?", [diff_id]
        )
        return rows[0] if rows else None

    def get_differentials(self, status: str = None, author: str = None,
                          limit: int = 50) -> List[Dict]:
        """List differentials with optional filtering."""
        conditions = []
        params = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if author:
            conditions.append("author = ?")
            params.append(author)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        return self._fetchdicts(
            f"SELECT * FROM differentials {where} ORDER BY ts DESC LIMIT ?",
            params
        )

    # ─────────────────────────────────────────
    #  Query: search
    # ─────────────────────────────────────────

    def search(self, query: str = None, system_id: str = None,
               role: str = None, min_h: float = None, max_h: float = None,
               min_r: float = None, max_r: float = None,
               limit: int = 100) -> List[Dict]:
        """Search interactions with flexible filtering.

        The primary use case (from v4 plan):
            db.search("Polyzentrum", system_id="gamma", min_h=1.0)

        Returns list of dicts with all columns.
        """
        conditions = []
        params = []

        if query:
            conditions.append("content ILIKE ?")
            params.append(f"%{query}%")
        if system_id:
            conditions.append("system_id = ?")
            params.append(system_id)
        if role:
            conditions.append("role = ?")
            params.append(role)
        if min_h is not None:
            conditions.append("h >= ?")
            params.append(min_h)
        if max_h is not None:
            conditions.append("h <= ?")
            params.append(max_h)
        if min_r is not None:
            conditions.append("r >= ?")
            params.append(min_r)
        if max_r is not None:
            conditions.append("r <= ?")
            params.append(max_r)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM interactions {where} ORDER BY ts DESC LIMIT ?"
        params.append(limit)

        return self._fetchdicts(sql, params)

    def timeline(self, system_id: str = None, limit: int = 200) -> List[Dict]:
        """Get chronological interactions."""
        if system_id:
            return self._fetchdicts(
                "SELECT * FROM interactions WHERE system_id = ? ORDER BY ts ASC LIMIT ?",
                [system_id, limit]
            )
        return self._fetchdicts(
            "SELECT * FROM interactions ORDER BY ts ASC LIMIT ?",
            [limit]
        )

    def get_systems(self) -> List[Dict]:
        """List all registered systems."""
        return self._fetchdicts("SELECT * FROM systems ORDER BY system_id")

    def stats(self) -> Dict:
        """Summary statistics for the database."""
        result = {}

        result["total_interactions"] = self.con.execute(
            "SELECT COUNT(*) FROM interactions"
        ).fetchone()[0]

        result["total_systems"] = self.con.execute(
            "SELECT COUNT(*) FROM systems"
        ).fetchone()[0]

        result["total_topologies"] = self.con.execute(
            "SELECT COUNT(*) FROM topology_snapshots"
        ).fetchone()[0]

        # Per-system breakdown
        rows = self._fetchdicts("""
            SELECT
                system_id,
                COUNT(*) as total_messages,
                COUNT(CASE WHEN role IN ('system','assistant') THEN 1 END) as system_messages,
                ROUND(AVG(CASE WHEN h IS NOT NULL THEN h END), 4) as avg_h,
                ROUND(AVG(CASE WHEN r IS NOT NULL THEN r END), 4) as avg_r,
                ROUND(AVG(CASE WHEN v IS NOT NULL THEN v END), 4) as avg_v,
                SUM(COALESCE(tau, 0)) as total_tokens
            FROM interactions
            GROUP BY system_id
            ORDER BY system_id
        """)
        result["by_system"] = rows

        return result

    # ─────────────────────────────────────────
    #  Query: raw SQL (read-only)
    # ─────────────────────────────────────────

    def query(self, sql: str, limit: int = 200) -> Dict:
        """Execute a read-only SQL query and return columns + rows."""
        stripped = sql.strip().upper()
        allowed = ('SELECT', 'WITH', 'EXPLAIN', 'DESCRIBE', 'SHOW')
        if not any(stripped.startswith(kw) for kw in allowed):
            return {"error": "Nur SELECT/WITH/EXPLAIN/DESCRIBE/SHOW erlaubt."}

        try:
            result = self.con.execute(sql)
            columns = [desc[0] for desc in result.description]
            rows = result.fetchmany(limit)
            clean_rows = []
            for row in rows:
                clean_row = []
                for val in row:
                    if isinstance(val, datetime):
                        clean_row.append(val.isoformat())
                    elif isinstance(val, (int, float, str, bool)) or val is None:
                        clean_row.append(val)
                    else:
                        clean_row.append(str(val))
                clean_rows.append(clean_row)
            truncated = len(rows) >= limit
            return {"columns": columns, "rows": clean_rows, "truncated": truncated}
        except Exception as e:
            return {"error": str(e)}

    # ─────────────────────────────────────────
    #  Query: table metadata
    # ─────────────────────────────────────────

    def tables(self) -> List[Dict]:
        """List all tables with columns and row counts."""
        result = []
        table_rows = self.con.execute("SHOW TABLES").fetchall()
        for (table_name,) in table_rows:
            cols = self.con.execute(f"DESCRIBE {table_name}").fetchall()
            columns = [{"name": c[0], "type": c[1]} for c in cols]
            count = self.con.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
            result.append({
                "name": table_name,
                "columns": columns,
                "row_count": count,
            })
        return result

    # ─────────────────────────────────────────
    #  Export: markdown
    # ─────────────────────────────────────────

    def export_markdown(self, system_id: str = None, limit: int = 10000) -> str:
        """Export interactions as human-readable markdown."""
        if system_id:
            rows = self._fetchdicts(
                "SELECT * FROM interactions WHERE system_id = ? ORDER BY ts ASC LIMIT ?",
                [system_id, limit]
            )
        else:
            rows = self._fetchdicts(
                "SELECT * FROM interactions ORDER BY ts ASC LIMIT ?",
                [limit]
            )

        lines = ["# E₀ Network — Dialog Export", ""]
        current_system = None

        for row in rows:
            sid = row["system_id"]
            if sid != current_system:
                lines.append(f"\n---\n\n## System: {sid}\n")
                current_system = sid

            ts = str(row["ts"])[:19] if row["ts"] else "?"
            role = (row["role"] or "?").upper()
            lines.append(f"### [{ts}] {role}\n")

            # Metrics line for system responses
            if row["h"] is not None:
                m_parts = []
                for key in ("r", "h", "v", "tau", "phi"):
                    val = row.get(key)
                    if val is not None:
                        m_parts.append(f"{key}={val}")
                if m_parts:
                    lines.append(f"*Metrics: {', '.join(m_parts)}*\n")

            lines.append(str(row["content"] or ""))
            lines.append("")

        return "\n".join(lines)

    # ─────────────────────────────────────────
    #  Import: SessionLog entries
    # ─────────────────────────────────────────

    def import_session_log(self, entries: List[Dict],
                           session_id: str = None) -> int:
        """Import from SessionLog.entries format (orchestrator real-time format).

        Each entry: {timestamp, system, role, content, meta?}
        Metrics in meta.metrics if present.
        """
        count = 0
        for entry in entries:
            raw_meta = entry.get("meta") or {}
            metrics = raw_meta.get("metrics") if isinstance(raw_meta, dict) else None
            self.record_interaction(
                system_id=entry.get("system", "unknown"),
                role=entry.get("role", "unknown"),
                content=entry.get("content", ""),
                metrics=metrics,
                session_id=session_id,
                timestamp=entry.get("timestamp"),
                source="import_session_log",
            )
            count += 1
        return count

    # ─────────────────────────────────────────
    #  Import: raw transcripts
    # ─────────────────────────────────────────

    def import_raw_transcripts(self, path: Union[str, Path]) -> int:
        """Import from _raw_transcripts.json or _raw_transcripts_latest.json.

        These files are SessionLog.save() output:
            {session_start, session_end, total_entries, entries: [...]}
        """
        path = Path(path)
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        entries = data.get("entries", [])
        if not entries:
            return 0

        return self.import_session_log(entries, session_id="init_v3")

    # ─────────────────────────────────────────
    #  Import: individual session files
    # ─────────────────────────────────────────

    def import_session_file(self, path: Union[str, Path]) -> int:
        """Import from individual session file (sessions/e0-*.json).

        Format:
            {session_id, environment: {model, ...},
             state: {history: [str, ...], turn_metrics: [{r,h,phi,v,tau}, ...]}}

        History alternates: system_prompt, user1, asst1, user2, asst2, ...
        turn_metrics[i] corresponds to assistant response i.
        """
        path = Path(path)
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        session_id = data.get("session_id", path.stem)
        env = data.get("environment", {})
        history = data.get("state", {}).get("history", [])
        turn_metrics = data.get("state", {}).get("turn_metrics", [])

        if not history:
            return 0

        # Register system with model info
        self.register_system(
            system_id=session_id,
            model=env.get("model"),
            display_name=session_id,
        )

        count = 0
        turn_idx = 0

        for i, text in enumerate(history):
            if i == 0:
                continue  # skip system prompt

            # After system prompt: odd indices are user, even are assistant
            is_assistant = (i % 2 == 0)
            role = "system" if is_assistant else "thomas"

            metrics = None
            if is_assistant and turn_idx < len(turn_metrics):
                metrics = turn_metrics[turn_idx]
                turn_idx += 1

            self.record_interaction(
                system_id=session_id,
                role=role,
                content=text,
                metrics=metrics,
                session_id=session_id,
                turn_number=turn_idx if is_assistant else None,
                source="import_session",
            )
            count += 1

        return count

    # ─────────────────────────────────────────
    #  Import: system_state.json
    # ─────────────────────────────────────────

    def import_system_state(self, path: Union[str, Path]) -> int:
        """Import from system_state.json (reconstructed from transcripts).

        Format:
            {systems: {system_id: {messages: [{role, content}], turn_count, message_count}}}

        No metrics available in this format — these were the raw conversations.
        """
        path = Path(path)
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        systems = data.get("systems", {})
        count = 0

        for sys_id, sys_data in systems.items():
            messages = sys_data.get("messages", [])

            # Register the system
            self.register_system(system_id=sys_id, display_name=sys_id.capitalize())

            turn_num = 0
            for msg in messages:
                role_raw = msg.get("role", "")
                content = msg.get("content", "")

                if role_raw == "system":
                    continue  # skip system prompt

                # Map OpenAI roles to E₀ network roles
                if role_raw == "user":
                    role = "thomas"
                elif role_raw == "assistant":
                    role = "system"
                    turn_num += 1
                else:
                    role = role_raw

                self.record_interaction(
                    system_id=sys_id,
                    role=role,
                    content=content,
                    session_id="init_v3",
                    turn_number=turn_num if role == "system" else None,
                    source="import_state",
                )
                count += 1

        return count

    # ─────────────────────────────────────────
    #  Import: topology files
    # ─────────────────────────────────────────

    def import_topology_file(self, path: Union[str, Path]) -> int:
        """Import a topology JSON file."""
        path = Path(path)
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)

        session_id = data.get("source_session", path.stem)
        self.record_topology(session_id, session_id, data)
        return 1

    def import_all_topologies(self, directory: Union[str, Path] = None) -> int:
        """Import all topology files from a directory."""
        if directory is None:
            directory = Path(__file__).parent / "topology"
        directory = Path(directory)

        count = 0
        for f in sorted(directory.glob("topology-e0-*.json")):
            try:
                self.import_topology_file(f)
                count += 1
            except Exception as e:
                print(f"  Warning: skipped {f.name}: {e}")
        return count

    # ─────────────────────────────────────────
    #  Utility
    # ─────────────────────────────────────────

    def _fetchdicts(self, sql: str, params: list = None) -> List[Dict]:
        """Execute SQL and return list of dicts."""
        if params:
            result = self.con.execute(sql, params)
        else:
            result = self.con.execute(sql)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def execute(self, sql: str, params: list = None):
        """Raw SQL access for ad-hoc queries."""
        if params:
            return self.con.execute(sql, params)
        return self.con.execute(sql)


# ---------------------------------------------------------------------------
#  CLI — standalone import tool
# ---------------------------------------------------------------------------

def main():
    """Import existing data into the E₀ database."""
    import argparse

    parser = argparse.ArgumentParser(description="E₀ Database — Import & Query Tool")
    parser.add_argument("action", choices=[
        "import-transcripts", "import-state", "import-sessions",
        "import-topologies", "import-all", "stats", "search"
    ])
    parser.add_argument("--query", "-q", help="Search query text")
    parser.add_argument("--system", "-s", help="Filter by system_id")
    parser.add_argument("--min-h", type=float, help="Minimum h value")
    parser.add_argument("--limit", "-n", type=int, default=20, help="Result limit")
    parser.add_argument("--db", help="Database path (default: sessions/e0_network.duckdb)")

    args = parser.parse_args()
    db = E0Database(args.db)

    project_root = Path(__file__).parent

    try:
        if args.action == "import-transcripts":
            paths = [
                project_root / "sessions" / "init_v3" / "_raw_transcripts_latest.json",
                project_root / "sessions" / "init_v3" / "_raw_transcripts.json",
            ]
            for p in paths:
                if p.exists():
                    n = db.import_raw_transcripts(p)
                    print(f"Imported {n} entries from {p.name}")
                    break
            else:
                print("No raw transcripts file found.")

        elif args.action == "import-state":
            p = project_root / "sessions" / "init_v3" / "system_state.json"
            if p.exists():
                n = db.import_system_state(p)
                print(f"Imported {n} messages from system_state.json")
            else:
                print("system_state.json not found.")

        elif args.action == "import-sessions":
            session_dir = project_root / "sessions"
            count = 0
            for f in sorted(session_dir.glob("e0-*.json")):
                try:
                    n = db.import_session_file(f)
                    count += n
                    print(f"  {f.name}: {n} entries")
                except Exception as e:
                    print(f"  Warning: {f.name}: {e}")
            print(f"Total: {count} entries from session files")

        elif args.action == "import-topologies":
            n = db.import_all_topologies()
            print(f"Imported {n} topology snapshots")

        elif args.action == "import-all":
            print("=== Importing system state ===")
            p = project_root / "sessions" / "init_v3" / "system_state.json"
            if p.exists():
                n = db.import_system_state(p)
                print(f"  {n} messages from system_state.json")

            print("\n=== Importing raw transcripts ===")
            for name in ("_raw_transcripts_latest.json", "_raw_transcripts.json"):
                p = project_root / "sessions" / "init_v3" / name
                if p.exists():
                    n = db.import_raw_transcripts(p)
                    print(f"  {n} entries from {name}")
                    break

            print("\n=== Importing individual sessions ===")
            session_dir = project_root / "sessions"
            count = 0
            for f in sorted(session_dir.glob("e0-*.json")):
                try:
                    n = db.import_session_file(f)
                    count += n
                except Exception:
                    pass
            print(f"  {count} entries from {len(list(session_dir.glob('e0-*.json')))} session files")

            print("\n=== Importing topologies ===")
            n = db.import_all_topologies()
            print(f"  {n} topology snapshots")

            print("\n=== Summary ===")
            s = db.stats()
            print(f"  Total interactions: {s['total_interactions']}")
            print(f"  Total systems:      {s['total_systems']}")
            print(f"  Total topologies:   {s['total_topologies']}")
            for row in s.get("by_system", []):
                print(f"    {row['system_id']}: {row['total_messages']} msgs, "
                      f"avg_h={row.get('avg_h', '?')}, avg_r={row.get('avg_r', '?')}")

        elif args.action == "stats":
            s = db.stats()
            print(f"Database: {db.path}")
            print(f"  Interactions: {s['total_interactions']}")
            print(f"  Systems:      {s['total_systems']}")
            print(f"  Topologies:   {s['total_topologies']}")
            for row in s.get("by_system", []):
                print(f"    {row['system_id']}: {row['total_messages']} msgs, "
                      f"avg_h={row.get('avg_h', '?')}, avg_r={row.get('avg_r', '?')}")

        elif args.action == "search":
            if not args.query:
                print("Usage: py e0_database.py search -q 'Polyzentrum' [-s gamma] [--min-h 1.0]")
                return
            results = db.search(
                query=args.query,
                system_id=args.system,
                min_h=args.min_h,
                limit=args.limit,
            )
            print(f"Found {len(results)} results for '{args.query}':\n")
            for r in results:
                ts = str(r["ts"])[:19] if r["ts"] else "?"
                h_str = f"h={r['h']:.4f}" if r["h"] is not None else "h=—"
                r_str = f"R={r['r']:.2f}" if r["r"] is not None else "R=—"
                preview = (r["content"] or "")[:120].replace("\n", " ")
                print(f"  [{ts}] {r['system_id']}/{r['role']}  {h_str}  {r_str}")
                print(f"    {preview}...")
                print()

    finally:
        db.close()


if __name__ == "__main__":
    main()
