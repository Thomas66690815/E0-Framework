"""
E₀ Keimzelle — Web Server
============================
Einfacher HTTP-Server für die Web-UI.
Bedient die UI-Dateien und bietet eine JSON-API.

Start: python -m keimzelle.server
Öffnet: http://localhost:3200
"""

from __future__ import annotations

import json
import os
import sys
import yaml
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs

from .storage import Storage
from .llm_adapter import LLMAdapter
from .models import Session, Delta, Note, Node, Interaction, PHASE_NAMES, PHASES
from .nodes import create_a3_light, create_theta_light, create_kappa_light
from .rounds import KoKognition, create_initial_delta
from .onboarding import setup_network, create_first_session

PORT = 3200
UI_DIR = Path(__file__).parent / "ui"

# Global state
storage: Storage = None
adapter: LLMAdapter = None
engine: KoKognition = None


def load_config() -> dict:
    config_path = Path("config.yml")
    if not config_path.exists():
        print("Keine config.yml gefunden. Bitte erstellen.")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class E0Handler(SimpleHTTPRequestHandler):
    """HTTP-Handler für UI + API."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # API-Routen
        if path.startswith("/api/"):
            self._handle_api_get(path, parse_qs(parsed.query))
            return

        # UI-Dateien
        if path == "/" or path == "":
            path = "/index.html"

        file_path = UI_DIR / path.lstrip("/")
        if file_path.exists() and file_path.is_file():
            self._serve_file(file_path)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            content_len = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_len)) if content_len > 0 else {}
            self._handle_api_post(path, body)
        else:
            self.send_error(404)

    def _serve_file(self, file_path: Path):
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon",
        }
        ext = file_path.suffix.lower()
        ct = content_types.get(ext, "application/octet-stream")

        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.end_headers()
        with open(file_path, "rb") as f:
            self.wfile.write(f.read())

    def _json_response(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_api_get(self, path: str, params: dict):
        global storage

        if path == "/api/status":
            network_name = storage.get_meta("network_name", "")
            self._json_response({
                "initialized": not storage.is_first_run(),
                "network_name": network_name,
            })

        elif path == "/api/sessions":
            sessions = storage.get_sessions()
            result = []
            for s in sessions:
                deltas = storage.get_deltas(s.id)
                result.append({
                    **s.to_dict(),
                    "phase_name": PHASE_NAMES.get(s.current_phase, s.current_phase),
                    "delta_count": len(deltas),
                })
            self._json_response(result)

        elif path == "/api/session":
            sid = params.get("id", [""])[0]
            session = storage.get_session(sid)
            if not session:
                self._json_response({"error": "Session nicht gefunden"}, 404)
                return
            deltas = storage.get_deltas(sid)
            delta_data = []
            for d in deltas:
                notes = storage.get_notes(d.id)
                note_data = []
                for n in notes:
                    node = storage.get_node(n.author_node_id)
                    note_data.append({
                        **n.to_dict(),
                        "author_name": node.name if node else "?",
                        "author_type": node.node_type if node else "?",
                        "phase_name": PHASE_NAMES.get(n.phase, n.phase),
                    })
                delta_data.append({
                    **d.to_dict(),
                    "notes": note_data,
                })
            self._json_response({
                "session": {
                    **session.to_dict(),
                    "phase_name": PHASE_NAMES.get(session.current_phase, session.current_phase),
                },
                "deltas": delta_data,
            })

        elif path == "/api/nodes":
            nodes = storage.get_nodes()
            self._json_response([n.to_dict() for n in nodes])

        else:
            self._json_response({"error": "Unbekannte Route"}, 404)

    def _handle_api_post(self, path: str, body: dict):
        global storage, adapter, engine

        if path == "/api/setup":
            # Netzwerk einrichten
            network_name = body.get("network_name", "E₀-Lokal")
            default_model = body.get("model", adapter.model)
            human, a3, theta, kappa = setup_network(storage, network_name, default_model)
            self._json_response({
                "ok": True,
                "network_name": network_name,
                "nodes": [n.to_dict() for n in [human, a3, theta, kappa]],
            })

        elif path == "/api/session/create":
            network_name = storage.get_meta("network_name", "E₀")
            topic = body.get("topic", "")
            name = body.get("name", "Neue Session")
            if not topic:
                self._json_response({"error": "Kein Thema angegeben"}, 400)
                return
            session = create_first_session(storage, network_name, topic)
            session.name = name
            storage.save_session(session)
            # Auto-Delta aus Topic
            human_nodes = storage.get_nodes("human")
            author_id = human_nodes[0].id if human_nodes else "unknown"
            delta = create_initial_delta(storage, session, topic, author_id)
            self._json_response({
                "session": session.to_dict(),
                "delta": delta.to_dict(),
            })

        elif path == "/api/delta/create":
            session_id = body.get("session_id", "")
            content = body.get("content", "")
            parent_id = body.get("parent_delta_id", None)
            if not content or not session_id:
                self._json_response({"error": "session_id und content erforderlich"}, 400)
                return
            human_nodes = storage.get_nodes("human")
            author_id = human_nodes[0].id if human_nodes else "unknown"
            delta = Delta(
                content=content,
                author_node_id=author_id,
                session_id=session_id,
                parent_delta_id=parent_id,
            )
            storage.save_delta(delta)
            storage.save_interaction(Interaction(
                session_id=session_id,
                from_node_id=author_id,
                action="set_delta",
                reference_id=delta.id,
            ))
            self._json_response({"delta": delta.to_dict()})

        elif path == "/api/round/run":
            # Eine Phase durchführen
            session_id = body.get("session_id", "")
            delta_id = body.get("delta_id", "")
            human_input = body.get("human_input", "")

            session = storage.get_session(session_id)
            delta = storage.get_delta(delta_id)
            if not session or not delta:
                self._json_response({"error": "Session oder Delta nicht gefunden"}, 404)
                return

            llm_nodes = storage.get_nodes("llm")
            human_nodes = storage.get_nodes("human")
            human_node = human_nodes[0] if human_nodes else None

            notes = engine.run_phase(
                session, delta, llm_nodes,
                human_input=human_input,
                human_node=human_node,
            )

            # Notes mit Autorinfo
            note_data = []
            for n in notes:
                node = storage.get_node(n.author_node_id)
                note_data.append({
                    **n.to_dict(),
                    "author_name": node.name if node else "?",
                    "author_type": node.node_type if node else "?",
                    "phase_name": PHASE_NAMES.get(n.phase, n.phase),
                })

            self._json_response({
                "notes": note_data,
                "session": {
                    **session.to_dict(),
                    "phase_name": PHASE_NAMES.get(session.current_phase, session.current_phase),
                },
            })

        elif path == "/api/phase/advance":
            session_id = body.get("session_id", "")
            session = storage.get_session(session_id)
            if not session:
                self._json_response({"error": "Session nicht gefunden"}, 404)
                return
            engine.advance_phase(session)
            self._json_response({
                "session": {
                    **session.to_dict(),
                    "phase_name": PHASE_NAMES.get(session.current_phase, session.current_phase),
                },
            })

        elif path == "/api/respond":
            # Human-Note hinzufügen
            delta_id = body.get("delta_id", "")
            session_id = body.get("session_id", "")
            content = body.get("content", "")
            if not content or not delta_id:
                self._json_response({"error": "delta_id und content erforderlich"}, 400)
                return
            human_nodes = storage.get_nodes("human")
            author_id = human_nodes[0].id if human_nodes else "unknown"
            session = storage.get_session(session_id)
            note = Note(
                delta_id=delta_id,
                author_node_id=author_id,
                content=content,
                round_number=session.current_round if session else 1,
                phase=session.current_phase if session else "open",
            )
            storage.save_note(note)
            if session:
                storage.save_interaction(Interaction(
                    session_id=session.id,
                    from_node_id=author_id,
                    action="respond",
                    reference_id=note.id,
                ))
            node = storage.get_node(author_id)
            self._json_response({
                **note.to_dict(),
                "author_name": node.name if node else "Du",
                "author_type": "human",
                "phase_name": PHASE_NAMES.get(note.phase, note.phase),
            })

        elif path == "/api/discourse":
            # Diskurs-Modus: Ein oder alle Knoten antworten
            session_id = body.get("session_id", "")
            delta_id = body.get("delta_id", "")
            human_input = body.get("human_input", "")
            target = body.get("target", "all")
            tool = body.get("tool", None)

            session = storage.get_session(session_id)
            delta = storage.get_delta(delta_id)
            if not session or not delta:
                self._json_response({"error": "Session oder Delta nicht gefunden"}, 404)
                return

            human_nodes = storage.get_nodes("human")
            human_node = human_nodes[0] if human_nodes else None

            if target == "all":
                llm_nodes = storage.get_nodes("llm")
                notes = engine.run_discourse_round(
                    session, delta, llm_nodes,
                    human_input=human_input,
                    human_node=human_node,
                    tool=tool,
                )
            else:
                target_node = storage.get_node(target)
                if not target_node:
                    self._json_response({"error": f"Knoten '{target}' nicht gefunden"}, 404)
                    return
                notes = engine.run_turn(
                    session, delta, target_node,
                    human_input=human_input,
                    human_node=human_node,
                    tool=tool,
                )

            note_data = []
            for n in notes:
                node = storage.get_node(n.author_node_id)
                note_data.append({
                    **n.to_dict(),
                    "author_name": node.name if node else "?",
                    "author_type": node.node_type if node else "?",
                    "phase_name": PHASE_NAMES.get(n.phase, n.phase),
                })

            self._json_response({
                "notes": note_data,
                "session": {
                    **session.to_dict(),
                    "phase_name": PHASE_NAMES.get(session.current_phase, session.current_phase),
                },
            })

        else:
            self._json_response({"error": "Unbekannte Route"}, 404)

    def log_message(self, format, *args):
        super().log_message(format, *args)


def main():
    global storage, adapter, engine

    config = load_config()

    llm_cfg = config.get("llm", {})
    storage = Storage(config.get("storage", {}).get("path", "data/keimzelle.db"))
    adapter = LLMAdapter(
        provider=llm_cfg.get("provider", "openai"),
        api_key=llm_cfg.get("api_key", ""),
        base_url=llm_cfg.get("base_url", ""),
        model=llm_cfg.get("model", "gpt-4o"),
    )
    engine = KoKognition(storage, adapter)

    server = HTTPServer(("", PORT), E0Handler)
    print(f"\n  E₀ Keimzelle — Web-UI")
    print(f"  http://localhost:{PORT}")
    print(f"  Strg+C zum Beenden\n")

    # Browser nur öffnen wenn nicht headless
    if not os.environ.get("E0_HEADLESS"):
        try:
            import webbrowser
            import threading
            threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
        except Exception:
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server beendet.\n")
    finally:
        storage.close()


if __name__ == "__main__":
    main()
