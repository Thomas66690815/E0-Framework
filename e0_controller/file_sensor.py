"""
E₀ FileSensor (C305)
=====================
Batch inscription source for E₀ Landscapes.

Design principle:
    File upload = World → E₀ (external data flows INTO Historization).
    Contrast with E2Port = E₀ → World (E₀ acts, world reports back).
    FileSensor lives on the E₂ boundary as a READ-only sensor:
    it injects prior knowledge without performing any navigation.

Supported formats:

    CSV — rows of historical observations:
        source,target,outcome
            → direct bulk inscription
        source,target            (no outcome column)
            → topology-only; all edges added with PARTIAL (neutral prior)

    JSON — structured knowledge:
        {"edges": [{"from": "A", "to": "B", "delta": 1.0,
                    "resistance": 0.5, "outcome": "success"}, ...]}
            → topology + optional inscriptions
        Subset of LandscapeBootstrapper DomainSpec — if "nodes" key present,
        spec is forwarded to build_from_spec() (no LLM, no Historization seeding).

    TEXT — free-form natural language:
        Forwarded to LandscapeBootstrapper for LLM-based topology extraction.
        Requires call_fn (LLM callable). No inscriptions are created.

InjectionReport (return type):
    edges_added     — new edges added to the Landscape
    inscriptions    — Historization updates performed
    skipped         — rows/entries skipped (malformed, self-loops, etc.)
    warnings        — human-readable notes

Usage:
    from e0_controller.file_sensor import FileSensor, parse_outcome_str

    L = Landscape()
    sensor = FileSensor(L)

    # CSV upload
    report = sensor.inject_csv(csv_text)
    print(report.edges_added, report.inscriptions)

    # JSON upload
    report = sensor.inject_json(json_text)

    # TEXT upload (requires LLM call_fn)
    report = sensor.inject_text(text, call_fn=my_llm)

    # generic entry-point (format auto-detected)
    report = sensor.inject(raw_bytes_or_str, hint="csv")
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .landscape import Landscape
from .primitives import Edge, Outcome


# ──────────────────────────────────────────────────────────────────────────────
# 1. Return type
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class InjectionReport:
    """Summary of a FileSensor injection operation."""
    edges_added: int = 0
    inscriptions: int = 0
    skipped: int = 0
    warnings: List[str] = field(default_factory=list)

    def merge(self, other: "InjectionReport") -> "InjectionReport":
        """Combine two reports into one (used when processing multi-chunk input)."""
        return InjectionReport(
            edges_added=self.edges_added + other.edges_added,
            inscriptions=self.inscriptions + other.inscriptions,
            skipped=self.skipped + other.skipped,
            warnings=self.warnings + other.warnings,
        )

    def __repr__(self) -> str:
        return (
            f"InjectionReport(edges_added={self.edges_added}, "
            f"inscriptions={self.inscriptions}, skipped={self.skipped}, "
            f"warnings={len(self.warnings)})"
        )


# ──────────────────────────────────────────────────────────────────────────────
# 2. Helpers
# ──────────────────────────────────────────────────────────────────────────────

_OUTCOME_MAP: Dict[str, Outcome] = {
    "success": Outcome.SUCCESS,
    "ok": Outcome.SUCCESS,
    "1": Outcome.SUCCESS,
    "true": Outcome.SUCCESS,
    "failure": Outcome.FAILURE,
    "fail": Outcome.FAILURE,
    "error": Outcome.FAILURE,
    "0": Outcome.FAILURE,
    "false": Outcome.FAILURE,
    "partial": Outcome.PARTIAL,
    "p": Outcome.PARTIAL,
    "half": Outcome.PARTIAL,
}


def parse_outcome_str(s: str) -> Optional[Outcome]:
    """Map a string to Outcome. Returns None if unrecognised."""
    return _OUTCOME_MAP.get(s.strip().lower())


def _default_delta() -> float:
    return 1.0


def _default_resistance() -> float:
    return 0.3


# ──────────────────────────────────────────────────────────────────────────────
# 3. FileSensor
# ──────────────────────────────────────────────────────────────────────────────

class FileSensor:
    """
    Injects file-sourced knowledge into a Landscape's Historization.

    The sensor is stateless beyond holding a reference to the Landscape.
    All injection methods are idempotent with respect to topology:
    adding the same edge twice is a no-op (existing delta/resistance kept).
    """

    def __init__(
        self,
        landscape: Landscape,
        default_delta: float = 1.0,
        default_resistance: float = 0.3,
    ) -> None:
        self._L = landscape
        self._default_delta = default_delta
        self._default_resistance = default_resistance

    # ── Public: format-specific entry points ─────────────────────────────────

    def inject_csv(self, text: str) -> InjectionReport:
        """
        Inject a CSV file.

        Accepted column layouts (header optional):
            source, target, outcome   — topology + inscriptions
            source, target            — topology only (PARTIAL prior)

        Header detection: if first row contains 'source'/'from' (case-insensitive)
        it is treated as a header and skipped.
        """
        report = InjectionReport()
        reader = csv.reader(io.StringIO(text.strip()))
        rows = list(reader)

        if not rows:
            report.warnings.append("CSV is empty")
            return report

        # Header detection
        first = [c.strip().lower() for c in rows[0]]
        has_header = any(c in ("source", "from", "src", "target", "to", "dst") for c in first)
        data_rows = rows[1:] if has_header else rows

        for i, row in enumerate(data_rows):
            # Strip whitespace from each cell
            row = [c.strip() for c in row]
            if not row or all(c == "" for c in row):
                continue

            if len(row) < 2:
                report.skipped += 1
                report.warnings.append(f"Row {i}: too few columns ({row!r})")
                continue

            src, tgt = row[0], row[1]

            if not src or not tgt:
                report.skipped += 1
                report.warnings.append(f"Row {i}: empty source or target")
                continue

            if src == tgt:
                report.skipped += 1
                report.warnings.append(f"Row {i}: self-loop '{src}' skipped")
                continue

            # Ensure edge exists
            new_edge = self._ensure_edge(src, tgt)
            if new_edge:
                report.edges_added += 1

            # Outcome (optional 3rd column)
            if len(row) >= 3 and row[2]:
                outcome = parse_outcome_str(row[2])
                if outcome is None:
                    report.skipped += 1
                    report.warnings.append(
                        f"Row {i}: unrecognised outcome '{row[2]}', row skipped"
                    )
                    continue
            else:
                outcome = Outcome.PARTIAL  # neutral prior when no outcome given

            self._inscribe(src, tgt, outcome)
            report.inscriptions += 1

        return report

    def inject_json(self, text: str) -> InjectionReport:
        """
        Inject a JSON file.

        Accepted schemas:

        Schema A — edge list:
            {"edges": [
                {"from": "A", "to": "B"},
                {"from": "A", "to": "B", "outcome": "success"},
                {"from": "A", "to": "B", "delta": 1.2, "resistance": 0.4, "outcome": "failure"},
                ...
            ]}

        Schema B — bootstrapper DomainSpec (nodes + edges with initial_U/F):
            {"nodes": [...], "edges": [...]}
            → topology created, no Historization inscriptions (use build_from_spec for that).

        Schema C — inscription log:
            {"traces": [{"source": "A", "target": "B", "outcome": "success"}, ...]}
        """
        report = InjectionReport()
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            report.warnings.append(f"JSON parse error: {exc}")
            report.skipped += 1
            return report

        if not isinstance(data, dict):
            report.warnings.append("JSON root must be an object")
            report.skipped += 1
            return report

        # Schema B: DomainSpec — delegate to topology-only path
        if "nodes" in data and "edges" in data:
            return self._inject_domain_spec(data)

        # Schema C: trace log
        if "traces" in data:
            return self._inject_trace_list(data["traces"])

        # Schema A: edge list
        if "edges" in data:
            return self._inject_edge_list(data["edges"])

        report.warnings.append("JSON must have 'edges', 'traces', or 'nodes'+'edges'")
        report.skipped += 1
        return report

    def inject_text(
        self,
        text: str,
        call_fn: Optional[Callable[..., Any]] = None,
    ) -> InjectionReport:
        """
        Inject free-form text via LandscapeBootstrapper.

        Requires call_fn (LLM callable compatible with bootstrapper.py).
        If call_fn is None, returns a report with a warning and no changes.

        The bootstrapper produces topology (nodes + edges with delta/resistance).
        No Historization inscriptions are created — E₀ starts from a cold prior
        on the new topology.
        """
        report = InjectionReport()
        if call_fn is None:
            report.warnings.append(
                "inject_text requires call_fn (LLM callable). No changes made."
            )
            return report

        try:
            from .bootstrapper import LandscapeBootstrapper
        except ImportError as exc:
            report.warnings.append(f"LandscapeBootstrapper unavailable: {exc}")
            return report

        try:
            bootstrapper = LandscapeBootstrapper(call_fn=call_fn)
            spec_dict = bootstrapper.extract_spec(text)
            sub_report = self._inject_domain_spec(spec_dict)
            report = report.merge(sub_report)
        except Exception as exc:  # noqa: BLE001
            report.warnings.append(f"LandscapeBootstrapper error: {exc}")

        return report

    def inject(
        self,
        content: Any,
        hint: Optional[str] = None,
        call_fn: Optional[Callable[..., Any]] = None,
    ) -> InjectionReport:
        """
        Generic entry point — format auto-detected or guided by hint.

        hint: "csv" | "json" | "text" | None (auto-detect)
        content: str or bytes
        """
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        if not isinstance(content, str):
            r = InjectionReport()
            r.warnings.append(f"Unsupported content type: {type(content)}")
            r.skipped += 1
            return r

        fmt = (hint or "").lower().strip()

        if fmt == "csv":
            return self.inject_csv(content)
        if fmt == "json":
            return self.inject_json(content)
        if fmt == "text":
            return self.inject_text(content, call_fn=call_fn)

        # Auto-detect
        stripped = content.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            return self.inject_json(stripped)
        # Heuristic: if first line has 1–2 commas per row → CSV
        lines = [l for l in stripped.splitlines() if l.strip()]
        if lines:
            comma_counts = [l.count(",") for l in lines[:5]]
            avg_commas = sum(comma_counts) / len(comma_counts)
            if 1 <= avg_commas <= 4:
                return self.inject_csv(stripped)

        return self.inject_text(stripped, call_fn=call_fn)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _ensure_edge(self, src: str, tgt: str) -> bool:
        """Add edge if absent. Returns True if a new edge was created."""
        existing = {(e.source, e.target) for e in self._L.edges}
        if (src, tgt) not in existing:
            self._L.add_edge(src, tgt,
                             delta=self._default_delta,
                             resistance=self._default_resistance)
            return True
        return False

    def _inscribe(self, src: str, tgt: str, outcome: Outcome) -> None:
        """Record one observation in Historization."""
        self._L.historization.update(Edge(src, tgt), outcome)

    def _inject_edge_list(self, edges: Any) -> InjectionReport:
        """Process Schema A: list of edge dicts."""
        report = InjectionReport()
        if not isinstance(edges, list):
            report.warnings.append("'edges' must be a list")
            report.skipped += 1
            return report

        for i, entry in enumerate(edges):
            if not isinstance(entry, dict):
                report.skipped += 1
                report.warnings.append(f"Edge {i}: not a dict")
                continue

            src = entry.get("from") or entry.get("source") or ""
            tgt = entry.get("to") or entry.get("target") or ""
            src, tgt = str(src).strip(), str(tgt).strip()

            if not src or not tgt:
                report.skipped += 1
                report.warnings.append(f"Edge {i}: missing source/target")
                continue

            if src == tgt:
                report.skipped += 1
                report.warnings.append(f"Edge {i}: self-loop '{src}' skipped")
                continue

            # Optional structural params
            delta = float(entry.get("delta", self._default_delta))
            resistance = float(entry.get("resistance", self._default_resistance))

            existing = {(e.source, e.target) for e in self._L.edges}
            if (src, tgt) not in existing:
                self._L.add_edge(src, tgt, delta=delta, resistance=resistance)
                report.edges_added += 1

            # Optional outcome
            outcome_raw = entry.get("outcome")
            if outcome_raw is not None:
                outcome = parse_outcome_str(str(outcome_raw))
                if outcome is None:
                    report.skipped += 1
                    report.warnings.append(
                        f"Edge {i}: unrecognised outcome '{outcome_raw}'"
                    )
                    continue
                self._inscribe(src, tgt, outcome)
                report.inscriptions += 1

        return report

    def _inject_trace_list(self, traces: Any) -> InjectionReport:
        """Process Schema C: list of trace dicts."""
        report = InjectionReport()
        if not isinstance(traces, list):
            report.warnings.append("'traces' must be a list")
            report.skipped += 1
            return report

        for i, entry in enumerate(traces):
            if not isinstance(entry, dict):
                report.skipped += 1
                continue

            src = entry.get("source") or entry.get("from") or ""
            tgt = entry.get("target") or entry.get("to") or ""
            src, tgt = str(src).strip(), str(tgt).strip()

            if not src or not tgt or src == tgt:
                report.skipped += 1
                continue

            outcome_raw = entry.get("outcome", "")
            outcome = parse_outcome_str(str(outcome_raw))
            if outcome is None:
                report.skipped += 1
                report.warnings.append(
                    f"Trace {i}: unrecognised outcome '{outcome_raw}'"
                )
                continue

            new_edge = self._ensure_edge(src, tgt)
            if new_edge:
                report.edges_added += 1

            self._inscribe(src, tgt, outcome)
            report.inscriptions += 1

        return report

    def _inject_domain_spec(self, spec: Dict[str, Any]) -> InjectionReport:
        """
        Process Schema B (DomainSpec subset): topology only.
        Creates edges from the spec, no Historization inscriptions.
        """
        report = InjectionReport()
        edges = spec.get("edges", [])
        if not isinstance(edges, list):
            report.warnings.append("DomainSpec 'edges' must be a list")
            return report

        for i, entry in enumerate(edges):
            if not isinstance(entry, dict):
                report.skipped += 1
                continue

            src = entry.get("from") or entry.get("source") or ""
            tgt = entry.get("to") or entry.get("target") or ""
            src, tgt = str(src).strip(), str(tgt).strip()

            if not src or not tgt or src == tgt:
                report.skipped += 1
                report.warnings.append(f"DomainSpec edge {i}: invalid source/target")
                continue

            delta = float(entry.get("delta", self._default_delta))
            resistance = float(entry.get("resistance", self._default_resistance))

            existing = {(e.source, e.target) for e in self._L.edges}
            if (src, tgt) not in existing:
                self._L.add_edge(src, tgt, delta=delta, resistance=resistance)
                report.edges_added += 1

        return report

    # ── Introspection ─────────────────────────────────────────────────────────

    def landscape_summary(self) -> Dict[str, Any]:
        """Quick summary of the current landscape state."""
        h = self._L.historization
        edges = list(self._L.edges)
        total_inscriptions = sum(
            h._U.get(e, 0.0) + h._F.get(e, 0.0)
            for e in edges
        )
        return {
            "states": len(self._L.states),
            "edges": len(edges),
            "total_inscriptions": total_inscriptions,
        }
