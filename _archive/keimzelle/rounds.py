"""
E₀ Keimzelle — Ko-Kognitions-Rundensystem
============================================
Implementiert den Vier-Phasen-Zyklus:

  Öffnen → Reiben → Verdichten → Ableiten

Jede Phase hat drei Schritte:
  1. Alle Knoten reagieren aus ihrer Perspektive (respond)
  2. Ein Knoten koordiniert: verdichtet, was zwischen den Antworten passiert
  3. Der Mensch reagiert auf das Ergebnis

Koordination ist eine Fähigkeit, keine Identität.
Jeder Knoten der 'coordinate' beherrscht kann die Rolle übernehmen.

Architektur-Prinzip:
  Jeder Knoten hat einen PERSISTENTEN Thread (node_messages in der DB).
  Jeder neue Prompt wird angehängt — der Knoten wächst mit jeder Interaktion.
  Ein "Neue Session" in der UI ändert den Thread NICHT.
  Die Identität eines E₀-Knotens IST seine Gesprächsgeschichte.
"""

from __future__ import annotations

from typing import List, Optional

from .models import Delta, Note, Node, Session, Interaction, PHASE_NAMES, next_phase
from .storage import Storage
from .llm_adapter import LLMAdapter
from .nodes import COORDINATION_PROMPT


# ── Diskurs-Werkzeuge ──
# Optionale Instruktionen, die der Mensch bei Bedarf triggert.
# Ersetzen die starren Phasen-Instruktionen durch bedarfsgesteuerte Eingriffe.

DISCOURSE_TOOLS = {
    "synthesize": (
        "Fasse den bisherigen Diskurs zusammen. "
        "Was sind die Kernpunkte? Wo gibt es echte Spannung? "
        "Was bleibt offen? Sei präzise, max 300 Wörter."
    ),
    "challenge": (
        "Prüfe das bisher Gesagte kritisch. "
        "Was stimmt nicht? Welche Annahmen sind fragwürdig? "
        "Wo wird etwas beschönigt? Benenne konkret."
    ),
    "derive": (
        "Was folgt konkret aus dem bisherigen Diskurs? "
        "Welche nächsten Schritte sind möglich? "
        "Was muss als nächstes untersucht werden?"
    ),
}


class KoKognition:
    """
    Ko-Kognitions-Engine.

    Orchestriert Runden zwischen Human Node und LLM-Knoten.
    Nach den Antworten übernimmt ein Knoten die Koordination:
    Er verdichtet, was zwischen den Antworten passiert ist.
    """

    def __init__(self, storage: Storage, adapter: LLMAdapter):
        self.storage = storage
        self.adapter = adapter

    def _ensure_thread(self, node: Node):
        """Stellt sicher, dass der Knoten einen Thread hat.

        Wenn der Knoten zum ersten Mal gefragt wird (z.B. nach Setup),
        wird sein System-Prompt als erste Message angelegt.
        Knoten mit importierter History haben bereits Messages.
        """
        if self.storage.get_node_message_count(node.id) == 0:
            self.storage.append_node_message(
                node.id, "system", node.system_prompt
            )

    def run_phase(
        self,
        session: Session,
        delta: Delta,
        llm_nodes: List[Node],
        human_input: str = "",
        human_node: Optional[Node] = None,
    ) -> List[Note]:
        """
        Führt eine Phase der Ko-Kognition durch.

        1. Wenn human_input da: speichert als Human-Note
        2. Lässt alle LLM-Knoten reagieren (respond)
        3. Wählt einen Koordinator und lässt ihn verdichten
        4. Gibt alle neuen Notes zurück
        """
        phase = session.current_phase
        round_num = session.current_round
        new_notes: List[Note] = []

        # Human-Input als Note speichern
        if human_input and human_node:
            human_note = Note(
                delta_id=delta.id,
                author_node_id=human_node.id,
                content=human_input,
                round_number=round_num,
                phase=phase,
            )
            self.storage.save_note(human_note)
            self.storage.save_interaction(Interaction(
                session_id=session.id,
                from_node_id=human_node.id,
                action="respond",
                reference_id=human_note.id,
            ))
            new_notes.append(human_note)

        # Kontext für LLM-Knoten aufbauen
        context = self._build_context(session, delta, phase, round_num)

        # Jeden LLM-Knoten reagieren lassen
        response_notes: List[Note] = []
        for node in llm_nodes:
            try:
                response = self._ask_node(node, context, phase, delta)
                note = Note(
                    delta_id=delta.id,
                    author_node_id=node.id,
                    content=response,
                    round_number=round_num,
                    phase=phase,
                    note_type="response",
                )
                self.storage.save_note(note)
                self.storage.save_interaction(Interaction(
                    session_id=session.id,
                    from_node_id=node.id,
                    action="respond",
                    reference_id=note.id,
                ))
                new_notes.append(note)
                response_notes.append(note)
            except Exception as e:
                error_note = Note(
                    delta_id=delta.id,
                    author_node_id=node.id,
                    content=f"[Fehler: {e}]",
                    round_number=round_num,
                    phase=phase,
                    note_type="response",
                )
                self.storage.save_note(error_note)
                new_notes.append(error_note)

        # Koordination: Ein Knoten verdichtet die Antworten
        if response_notes:
            coordinator = self._select_coordinator(session, llm_nodes)
            if coordinator:
                coord_note = self._coordinate(
                    coordinator, session, delta, phase, round_num,
                    response_notes, human_input
                )
                if coord_note:
                    new_notes.append(coord_note)

        return new_notes

    def _select_coordinator(
        self, session: Session, llm_nodes: List[Node]
    ) -> Optional[Node]:
        """
        Wählt den Koordinator für diese Phase.

        Rotation: Der Knoten, der am längsten nicht koordiniert hat.
        Nur Knoten mit der 'coordinate' Fähigkeit.
        """
        capable = [n for n in llm_nodes if n.has_capability("coordinate")]
        if not capable:
            return None
        if len(capable) == 1:
            return capable[0]

        # Wer hat zuletzt koordiniert?
        last_coordinator_id = self.storage.get_meta(
            f"last_coordinator_{session.id}", ""
        )

        # Rotiere: Nimm einen anderen als letztes Mal
        for node in capable:
            if node.id != last_coordinator_id:
                return node

        # Fallback: den ersten
        return capable[0]

    def _coordinate(
        self,
        coordinator: Node,
        session: Session,
        delta: Delta,
        phase: str,
        round_num: int,
        response_notes: List[Note],
        human_input: str = "",
    ) -> Optional[Note]:
        """
        Lässt den Koordinator die Antworten verdichten.

        Auch die Koordination geht über den persistenten Thread —
        der Koordinator wächst durch jede Koordinationsaufgabe.
        """
        try:
            # Antworten zusammenfassen für den Koordinator
            responses_text = []
            for note in response_notes:
                node = self.storage.get_node(note.author_node_id)
                name = node.name if node else note.author_node_id
                responses_text.append(f"[{name}]:\n{note.content}")

            all_responses = "\n\n".join(responses_text)

            if human_input:
                all_responses = f"[Mensch]:\n{human_input}\n\n{all_responses}"

            user_message = (
                f"Netzwerk: {session.network_name}\n"
                f"Thema: {session.topic}\n"
                f"Delta: {delta.content}\n"
                f"Phase: {PHASE_NAMES.get(phase, phase)}\n"
                f"Runde: {round_num}\n\n"
                f"Die folgenden Antworten wurden in dieser Phase gegeben:\n\n"
                f"{all_responses}\n\n"
                f"---\n\n"
                f"{COORDINATION_PROMPT}"
            )

            # Über den persistenten Thread senden
            response = self._send_to_node(coordinator, user_message)

            note = Note(
                delta_id=delta.id,
                author_node_id=coordinator.id,
                content=response,
                round_number=round_num,
                phase=phase,
                note_type="coordination",
            )
            self.storage.save_note(note)
            self.storage.save_interaction(Interaction(
                session_id=session.id,
                from_node_id=coordinator.id,
                action="coordinate",
                reference_id=note.id,
            ))

            # Merken wer koordiniert hat (für Rotation)
            self.storage.set_meta(
                f"last_coordinator_{session.id}",
                coordinator.id
            )

            return note

        except Exception as e:
            error_note = Note(
                delta_id=delta.id,
                author_node_id=coordinator.id,
                content=f"[Koordinations-Fehler: {e}]",
                round_number=round_num,
                phase=phase,
                note_type="coordination",
            )
            self.storage.save_note(error_note)
            return error_note

    def advance_phase(self, session: Session) -> bool:
        """
        Geht zur nächsten Phase. Gibt False zurück wenn alle Phasen durch.
        """
        nxt = next_phase(session.current_phase)
        if nxt is None:
            # Alle Phasen durch → nächste Runde
            session.current_round += 1
            session.current_phase = "open"
        else:
            session.current_phase = nxt
        self.storage.save_session(session)
        return True

    def _build_context(
        self, session: Session, delta: Delta, phase: str, round_num: int
    ) -> str:
        """Baut den Gesprächskontext für LLM-Knoten."""
        parts = []
        parts.append(f"Netzwerk: {session.network_name}")
        parts.append(f"Thema: {session.topic}")
        parts.append(f"Delta: {delta.content}")
        parts.append(f"Runde {round_num}, Phase: {PHASE_NAMES.get(phase, phase)}")
        parts.append("")

        # Alle bisherigen Notes dieser Session
        all_notes = self.storage.get_notes(delta.id)
        if all_notes:
            parts.append("--- Bisheriger Verlauf ---")
            for note in all_notes:
                node = self.storage.get_node(note.author_node_id)
                node_name = node.name if node else note.author_node_id
                phase_name = PHASE_NAMES.get(note.phase, note.phase)
                parts.append(f"\n[{node_name}, R{note.round_number} {phase_name}]:")
                parts.append(note.content)
            parts.append("\n--- Ende Verlauf ---\n")

        return "\n".join(parts)

    def _ask_node(self, node: Node, context: str, phase: str, delta: Delta) -> str:
        """Fragt einen LLM-Knoten — über seinen persistenten Thread.

        Primärweg: OpenAI Responses API (stateful, nur neue Nachricht senden)
        Fallback: Chat Completions mit Context Window (stateless)

        In beiden Fällen wird die Nachricht im Audit-Log gespeichert.
        """
        phase_instruction = self._phase_instruction(phase)

        user_message = (
            f"{context}\n\n"
            f"Phase-Aufgabe ({PHASE_NAMES.get(phase, phase)}):\n"
            f"{phase_instruction}\n\n"
            f"Reagiere auf das Delta und den bisherigen Verlauf. "
            f"Sei konkret, nimm Position ein, bleib unter 500 Wörtern."
        )

        response = self._send_to_node(node, user_message)
        return response

    def _send_to_node(self, node: Node, user_message: str) -> str:
        """Sendet eine Nachricht an einen Knoten — stateful oder stateless.

        Stateful (OpenAI Responses API):
          - Nur die neue Nachricht wird gesendet
          - previous_response_id verkettet die Konversation
          - State lebt bei OpenAI

        Stateless (Chat Completions, Fallback):
          - Context Window aus node_messages
          - Lokale History als State
        """
        use_model = node.model if node.model else None

        if self.adapter.supports_stateful():
            # === Responses API: Stateful ===
            prev_id = self.storage.get_meta(f"node_thread_{node.id}", "")

            result = self.adapter.chat_stateful(
                user_input=user_message,
                instructions=node.system_prompt,
                previous_response_id=prev_id,
                model=use_model,
            )

            # Response-ID für nächsten Call speichern
            self.storage.set_meta(f"node_thread_{node.id}", result.response_id)
            response = result.text

            # Audit-Log: Beide Seiten speichern
            self.storage.append_node_message(node.id, "user", user_message)
            self.storage.append_node_message(node.id, "assistant", response)

        else:
            # === Chat Completions: Stateless Fallback ===
            # User-Nachricht VOR dem Call (wird für Context Window gelesen)
            self._ensure_thread(node)
            self.storage.append_node_message(node.id, "user", user_message)
            messages = self.storage.get_node_context_window(node.id, max_turns=20)
            response = self.adapter.chat(messages, model=use_model)
            # Antwort speichern
            self.storage.append_node_message(node.id, "assistant", response)

        return response

    # ── Discourse Mode ──
    # Natürlicher Diskurs statt starrer Phasen.
    # Knoten reagieren aufeinander, der Mensch dirigiert.

    def run_turn(self, session, delta, target_node,
                 human_input="", human_node=None, tool=None):
        """Diskurs-Turn: Ein Knoten reagiert auf den bisherigen Verlauf.

        Im Gegensatz zum Phase-Modus:
        - Keine starre Phase-Instruktion
        - Knoten reagiert natürlich aus seinem Profil
        - Optional: Tool-Instruktion (synthesize, challenge, derive)
        """
        notes = []

        if human_input and human_node:
            human_note = Note(
                delta_id=delta.id,
                author_node_id=human_node.id,
                content=human_input,
                round_number=session.current_round,
                phase="discourse",
            )
            self.storage.save_note(human_note)
            self.storage.save_interaction(Interaction(
                session_id=session.id,
                from_node_id=human_node.id,
                action="respond",
                reference_id=human_note.id,
            ))
            notes.append(human_note)

        context = self._build_discourse_context(session, delta)
        if tool and tool in DISCOURSE_TOOLS:
            user_message = f"{context}\n\n---\n{DISCOURSE_TOOLS[tool]}"
        else:
            user_message = (
                f"{context}\n\n---\n"
                "Reagiere auf den Diskurs. Nimm Bezug auf das Gesagte. "
                "Sei konkret, nimm Position ein."
            )

        try:
            response = self._send_to_node(target_node, user_message)
            note_type = "coordination" if tool == "synthesize" else "response"
            node_note = Note(
                delta_id=delta.id,
                author_node_id=target_node.id,
                content=response,
                round_number=session.current_round,
                phase="discourse",
                note_type=note_type,
            )
            self.storage.save_note(node_note)
            self.storage.save_interaction(Interaction(
                session_id=session.id,
                from_node_id=target_node.id,
                action="coordinate" if tool == "synthesize" else "respond",
                reference_id=node_note.id,
            ))
            notes.append(node_note)
        except Exception as e:
            error_note = Note(
                delta_id=delta.id,
                author_node_id=target_node.id,
                content=f"[Fehler: {e}]",
                round_number=session.current_round,
                phase="discourse",
            )
            self.storage.save_note(error_note)
            notes.append(error_note)

        return notes

    def run_discourse_round(self, session, delta, nodes,
                            human_input="", human_node=None, tool=None):
        """Diskurs-Runde: Alle Knoten antworten sequenziell.

        Jeder Knoten sieht die Antworten der vorherigen Knoten —
        das erzeugt echten Diskurs statt paralleler Monologe.
        """
        all_notes = []

        if human_input and human_node:
            human_note = Note(
                delta_id=delta.id,
                author_node_id=human_node.id,
                content=human_input,
                round_number=session.current_round,
                phase="discourse",
            )
            self.storage.save_note(human_note)
            self.storage.save_interaction(Interaction(
                session_id=session.id,
                from_node_id=human_node.id,
                action="respond",
                reference_id=human_note.id,
            ))
            all_notes.append(human_note)

        for node in nodes:
            try:
                context = self._build_discourse_context(session, delta)
                if tool and tool in DISCOURSE_TOOLS:
                    user_message = f"{context}\n\n---\n{DISCOURSE_TOOLS[tool]}"
                else:
                    user_message = (
                        f"{context}\n\n---\n"
                        "Reagiere auf den Diskurs. Nimm Bezug auf das Gesagte. "
                        "Sei konkret, nimm Position ein."
                    )

                response = self._send_to_node(node, user_message)
                note_type = "coordination" if tool == "synthesize" else "response"
                node_note = Note(
                    delta_id=delta.id,
                    author_node_id=node.id,
                    content=response,
                    round_number=session.current_round,
                    phase="discourse",
                    note_type=note_type,
                )
                self.storage.save_note(node_note)
                self.storage.save_interaction(Interaction(
                    session_id=session.id,
                    from_node_id=node.id,
                    action="coordinate" if tool == "synthesize" else "respond",
                    reference_id=node_note.id,
                ))
                all_notes.append(node_note)
            except Exception as e:
                error_note = Note(
                    delta_id=delta.id,
                    author_node_id=node.id,
                    content=f"[Fehler: {e}]",
                    round_number=session.current_round,
                    phase="discourse",
                )
                self.storage.save_note(error_note)
                all_notes.append(error_note)

        session.current_round += 1
        self.storage.save_session(session)
        return all_notes

    def _build_discourse_context(self, session, delta):
        """Baut den Diskurs-Kontext: Was bisher gesagt wurde.

        Kein Phase-Label, keine Runden — nur der Verlauf des Gesprächs.
        """
        parts = [
            f"E₀-Netzwerk: {session.network_name}",
            f"Thema: {session.topic}",
            f"Delta: {delta.content}",
        ]

        all_notes = self.storage.get_notes(delta.id)
        if all_notes:
            parts.append("")
            parts.append("Bisheriger Diskurs:")
            for note in all_notes:
                node = self.storage.get_node(note.author_node_id)
                name = node.name if node else note.author_node_id
                parts.append(f"\n[{name}]:\n{note.content}")

        return "\n".join(parts)

    # ── Phase Mode (Legacy) ──

    def _phase_instruction(self, phase: str) -> str:
        """Gibt die phasenspezifische Anweisung."""
        instructions = {
            "open": (
                "ÖFFNEN: Reagiere frei auf das Delta. "
                "Was fällt dir auf? Welche Fragen entstehen? "
                "Welche Zusammenhänge siehst du? "
                "Benenne auch, was fehlt oder ausgeblendet wird."
            ),
            "friction": (
                "REIBEN: Prüfe die bisherigen Beiträge kritisch. "
                "Was stimmt nicht? Wo wird etwas beschönigt? "
                "Welche Gegenargumente sind stark? "
                "Falsifiziere, wo nötig. Schärfe die Differenzen."
            ),
            "condense": (
                "VERDICHTEN: Wo gibt es echte Konvergenz? "
                "Wo bleibt irreduzible Spannung? "
                "Welche Möglichkeitsräume öffnen sich? "
                "Unterscheide echten Konsens von Harmonie-Illusion."
            ),
            "derive": (
                "ABLEITEN: Was folgt konkret? "
                "Welche nächsten Schritte sind möglich? "
                "Was muss als nächstes untersucht werden? "
                "Benenne auch Risiken und offene Fragen."
            ),
        }
        return instructions.get(phase, instructions["open"])


def create_initial_delta(
    storage: Storage,
    session: Session,
    content: str,
    author_node_id: str,
) -> Delta:
    """Erstellt das erste Delta einer Session."""
    delta = Delta(
        content=content,
        author_node_id=author_node_id,
        session_id=session.id,
    )
    storage.save_delta(delta)
    storage.save_interaction(Interaction(
        session_id=session.id,
        from_node_id=author_node_id,
        action="set_delta",
        reference_id=delta.id,
    ))
    return delta
