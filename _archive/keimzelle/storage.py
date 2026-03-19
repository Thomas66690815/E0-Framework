"""
E₀ Keimzelle — SQLite Storage
===============================
Persistenz für alle Kern-Entities.
Verwendet SQLite (stdlib) — keine externen Abhängigkeiten.

Architektur-Prinzip:
  Jeder E₀-Knoten hat eine persistente Message-History (node_messages).
  Das ist seine Identität — ein endloser Chat, kein stateless API-Call.
  Themen-Sessions (in der UI) ändern den Thread NICHT.
  Der Knoten wächst mit jeder Interaktion.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import List, Optional

from .models import Node, Delta, Note, Session, Interaction


DEFAULT_DB_PATH = Path("data") / "keimzelle.db"


class Storage:
    """SQLite-basierter Speicher für E₀-Keimzelle."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                name TEXT,
                node_type TEXT,
                role TEXT,
                system_prompt TEXT,
                model TEXT,
                capabilities TEXT DEFAULT 'respond',
                config TEXT DEFAULT '{}',
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT,
                topic TEXT,
                network_name TEXT,
                current_round INTEGER DEFAULT 1,
                current_phase TEXT DEFAULT 'open',
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS deltas (
                id TEXT PRIMARY KEY,
                content TEXT,
                author_node_id TEXT,
                session_id TEXT,
                parent_delta_id TEXT,
                tags TEXT DEFAULT '',
                created_at TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id),
                FOREIGN KEY (author_node_id) REFERENCES nodes(id)
            );

            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                delta_id TEXT,
                author_node_id TEXT,
                content TEXT,
                round_number INTEGER DEFAULT 1,
                phase TEXT DEFAULT 'open',
                note_type TEXT DEFAULT 'response',
                created_at TEXT,
                FOREIGN KEY (delta_id) REFERENCES deltas(id),
                FOREIGN KEY (author_node_id) REFERENCES nodes(id)
            );

            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                from_node_id TEXT,
                to_node_id TEXT,
                action TEXT,
                reference_id TEXT,
                created_at TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS network_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS node_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (node_id) REFERENCES nodes(id)
            );
        """)
        self.conn.commit()

    # ── Network Meta ──

    def set_meta(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO network_meta (key, value) VALUES (?, ?)",
            (key, value)
        )
        self.conn.commit()

    def get_meta(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM network_meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    # ── Nodes ──

    def save_node(self, node: Node):
        d = node.to_dict()
        d["config"] = json.dumps(d.get("config", {}))
        self.conn.execute("""
            INSERT OR REPLACE INTO nodes
            (id, name, node_type, role, system_prompt, model, capabilities, config, created_at)
            VALUES (:id, :name, :node_type, :role, :system_prompt, :model, :capabilities, :config, :created_at)
        """, d)
        self.conn.commit()

    def get_node(self, node_id: str) -> Optional[Node]:
        row = self.conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["config"] = json.loads(d.get("config", "{}"))
        # capabilities: komma-separiert in DB, Liste im Model
        if isinstance(d.get("capabilities"), str):
            d["capabilities"] = [c.strip() for c in d["capabilities"].split(",") if c.strip()]
        return Node.from_dict(d)

    def get_nodes(self, node_type: str = None) -> List[Node]:
        if node_type:
            rows = self.conn.execute("SELECT * FROM nodes WHERE node_type = ?", (node_type,)).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM nodes").fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["config"] = json.loads(d.get("config", "{}"))
            if isinstance(d.get("capabilities"), str):
                d["capabilities"] = [c.strip() for c in d["capabilities"].split(",") if c.strip()]
            result.append(Node.from_dict(d))
        return result

    # ── Sessions ──

    def save_session(self, session: Session):
        self.conn.execute("""
            INSERT OR REPLACE INTO sessions
            (id, name, topic, network_name, current_round, current_phase, created_at)
            VALUES (:id, :name, :topic, :network_name, :current_round, :current_phase, :created_at)
        """, session.to_dict())
        self.conn.commit()

    def get_session(self, session_id: str) -> Optional[Session]:
        row = self.conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return Session.from_dict(dict(row)) if row else None

    def get_sessions(self) -> List[Session]:
        rows = self.conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        return [Session.from_dict(dict(r)) for r in rows]

    def get_latest_session(self) -> Optional[Session]:
        row = self.conn.execute("SELECT * FROM sessions ORDER BY created_at DESC LIMIT 1").fetchone()
        return Session.from_dict(dict(row)) if row else None

    # ── Deltas ──

    def save_delta(self, delta: Delta):
        self.conn.execute("""
            INSERT OR REPLACE INTO deltas
            (id, content, author_node_id, session_id, parent_delta_id, tags, created_at)
            VALUES (:id, :content, :author_node_id, :session_id, :parent_delta_id, :tags, :created_at)
        """, delta.to_dict())
        self.conn.commit()

    def get_delta(self, delta_id: str) -> Optional[Delta]:
        row = self.conn.execute("SELECT * FROM deltas WHERE id = ?", (delta_id,)).fetchone()
        return Delta.from_dict(dict(row)) if row else None

    def get_deltas(self, session_id: str) -> List[Delta]:
        rows = self.conn.execute(
            "SELECT * FROM deltas WHERE session_id = ? ORDER BY created_at", (session_id,)
        ).fetchall()
        return [Delta.from_dict(dict(r)) for r in rows]

    # ── Notes ──

    def save_note(self, note: Note):
        self.conn.execute("""
            INSERT OR REPLACE INTO notes
            (id, delta_id, author_node_id, content, round_number, phase, note_type, created_at)
            VALUES (:id, :delta_id, :author_node_id, :content, :round_number, :phase, :note_type, :created_at)
        """, note.to_dict())
        self.conn.commit()

    def get_notes(self, delta_id: str, round_number: int = None, phase: str = None) -> List[Note]:
        query = "SELECT * FROM notes WHERE delta_id = ?"
        params: list = [delta_id]
        if round_number is not None:
            query += " AND round_number = ?"
            params.append(round_number)
        if phase:
            query += " AND phase = ?"
            params.append(phase)
        query += " ORDER BY created_at"
        rows = self.conn.execute(query, params).fetchall()
        return [Note.from_dict(dict(r)) for r in rows]

    # ── Interactions ──

    def save_interaction(self, interaction: Interaction):
        self.conn.execute("""
            INSERT OR REPLACE INTO interactions
            (id, session_id, from_node_id, to_node_id, action, reference_id, created_at)
            VALUES (:id, :session_id, :from_node_id, :to_node_id, :action, :reference_id, :created_at)
        """, interaction.to_dict())
        self.conn.commit()

    def get_interactions(self, session_id: str) -> List[Interaction]:
        rows = self.conn.execute(
            "SELECT * FROM interactions WHERE session_id = ? ORDER BY created_at",
            (session_id,)
        ).fetchall()
        return [Interaction.from_dict(dict(r)) for r in rows]

    # ── Utility ──

    def is_first_run(self) -> bool:
        """Prüft ob dies der allererste Start ist (kein Netzwerk eingerichtet)."""
        row = self.conn.execute("SELECT COUNT(*) as c FROM nodes").fetchone()
        return row["c"] == 0

    # ── Node Messages (persistenter Thread pro Knoten) ──

    def append_node_message(self, node_id: str, role: str, content: str):
        """Hängt eine Nachricht an den Thread eines Knotens an.

        Jeder Knoten hat einen endlosen Chat. Neue Nachrichten werden
        nur angehängt, nie gelöscht. Das ist die Identität des Knotens.
        """
        from datetime import datetime
        self.conn.execute(
            "INSERT INTO node_messages (node_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (node_id, role, content, datetime.utcnow().isoformat())
        )
        self.conn.commit()

    def get_node_messages(self, node_id: str) -> List[dict]:
        """Gibt ALLE Nachrichten eines Knotens zurück (chronologisch).

        Returns: Liste von {"role": "user"|"assistant"|"system", "content": "..."}
        """
        rows = self.conn.execute(
            "SELECT role, content FROM node_messages "
            "WHERE node_id = ? ORDER BY id ASC",
            (node_id,)
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def get_node_context_window(
        self, node_id: str, max_turns: int = 20
    ) -> List[dict]:
        """Gibt die letzten N Turns + System-Prompt zurück.

        Wie E0ChatClient._build_context_window():
        - System-Messages am Anfang bleiben IMMER
        - Die letzten max_turns user/assistant-Paare
        - Transparent für den Knoten: fühlt sich an wie endloser Chat

        Returns: Liste von {"role": ..., "content": ...}
        """
        all_msgs = self.get_node_messages(node_id)
        if not all_msgs:
            return []

        # System-Messages (Preamble) separieren
        preamble = []
        conversation = []
        for msg in all_msgs:
            if msg["role"] == "system" and not conversation:
                preamble.append(msg)
            else:
                conversation.append(msg)

        # User-Messages zählen für Turn-Begrenzung
        user_indices = [i for i, m in enumerate(conversation)
                        if m["role"] == "user"]

        if len(user_indices) <= max_turns:
            return preamble + conversation

        # Nur die letzten max_turns behalten
        cut_from = user_indices[-max_turns]
        return preamble + conversation[cut_from:]

    def get_node_message_count(self, node_id: str) -> int:
        """Wie viele Nachrichten hat ein Knoten insgesamt?"""
        row = self.conn.execute(
            "SELECT COUNT(*) as c FROM node_messages WHERE node_id = ?",
            (node_id,)
        ).fetchone()
        return row["c"]

    def close(self):
        self.conn.close()
