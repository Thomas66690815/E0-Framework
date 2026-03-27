"""
E₀ Provenance Log
==================
Records the full evidence chain from raw input to evaluation result.

The log captures every stage of the pipeline:

    Input Text
      → LLM Call  (prompt, response, model, timestamp)
        → Landscape Proposal  (states, edges JSON)
          → Materialized Landscape  (S_eff values, graph metrics)
            → Controller Run  (geometry, mode, params, trace)
              → Evaluation  (goal reached?, override count, comparison)

Each stage stores its input and output so the chain is:
- **Reproducible**: replay each step from archived data
- **Verifiable**: a third party can check prompt → response → landscape
- **Non-circularity auditable**: the LLM prompt is visible, the response archived

Usage
-----
    log = ProvenanceLog(source_id="beipackzettel-ibuprofen")
    log.record_input("Ibuprofen 400 mg ...")

    # Wrapping the LLM adapter:
    adapter = E0LLMAdapter(call_fn=log.wrap_call_fn(original_call_fn))
    proposal = adapter.build_landscape(text, start, goal)
    log.record_proposal(proposal)

    L = materialize_landscape(proposal)
    log.record_landscape(L, start, goal)

    ctrl = E0Controller(L, execute_fn, ...)
    trace = ctrl.run(start, goal=goal)
    log.record_run(trace, controller_config={...})

    log.record_evaluation({"goal_reached": True, ...})
    log.save("provenance/ibuprofen_run_001.json")
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .llm_adapter import LLMConfig, LandscapeProposal


# ── Stage Records ────────────────────────────────────────────────────────

@dataclass
class InputRecord:
    """Raw input text and its fingerprint."""
    text: str
    sha256: str                     # hash of the input text
    source_id: str = ""             # human label (e.g. "beipackzettel-ibuprofen")
    timestamp: str = ""

    def __post_init__(self):
        if not self.sha256:
            self.sha256 = hashlib.sha256(self.text.encode()).hexdigest()
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class LLMCallRecord:
    """One LLM call with full prompt and response."""
    system_prompt: str
    user_prompt: str
    raw_response: str
    model: str
    temperature: float
    timestamp: str = ""
    duration_ms: Optional[float] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class ProposalRecord:
    """The landscape proposal as returned by the LLM (post-parse)."""
    states: List[str]
    edges: List[Dict[str, Any]]
    state_count: int = 0
    edge_count: int = 0

    def __post_init__(self):
        self.state_count = len(self.states)
        self.edge_count = len(self.edges)


@dataclass
class LandscapeRecord:
    """Materialized landscape metrics."""
    state_count: int
    edge_count: int
    start: str
    goal: str
    s_eff_values: Dict[str, float]    # "A→B" → S_eff
    goal_reachable: bool


@dataclass
class RunRecord:
    """Controller run trace summary."""
    path: List[str]
    step_count: int
    goal_reached: bool
    total_tension: float
    hybrid_override_count: int
    controller_config: Dict[str, Any]   # geometry, mode, horizon, ...


@dataclass
class EvaluationRecord:
    """Final evaluation — free-form dict for flexibility."""
    findings: Dict[str, Any]
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


# ── Main Log ─────────────────────────────────────────────────────────────

@dataclass
class ProvenanceLog:
    """Full evidence chain for one E₀ pipeline execution.

    Records each stage sequentially.  Serializable to JSON for archival.
    """
    source_id: str = ""
    input: Optional[InputRecord] = None
    llm_calls: List[LLMCallRecord] = field(default_factory=list)
    proposal: Optional[ProposalRecord] = None
    landscape: Optional[LandscapeRecord] = None
    runs: List[RunRecord] = field(default_factory=list)
    evaluation: Optional[EvaluationRecord] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Recording methods ────────────────────────────────────────────

    def record_input(self, text: str, source_id: str = "") -> None:
        """Record the raw input text."""
        sid = source_id or self.source_id
        self.input = InputRecord(text=text, sha256="", source_id=sid)
        if sid:
            self.source_id = sid

    def record_proposal(self, proposal: LandscapeProposal) -> None:
        """Record the landscape proposal (post-LLM-parse)."""
        self.proposal = ProposalRecord(
            states=list(proposal.states),
            edges=list(proposal.edges),
        )

    def record_landscape(
        self,
        landscape: Any,   # Landscape — avoid circular import at module level
        start: str,
        goal: str,
    ) -> None:
        """Record materialized landscape metrics."""
        s_eff_map: Dict[str, float] = {}
        for state in landscape.states:
            for neighbor in landscape.admissible_neighbors(state):
                key = f"{state}\u2192{neighbor}"
                s_eff_map[key] = landscape.effective_tension(state, neighbor)

        # Check goal reachability
        from .graph_validation import goal_reachable
        reachable = goal_reachable(landscape, start, goal)

        self.landscape = LandscapeRecord(
            state_count=len(landscape.states),
            edge_count=sum(
                len(landscape.admissible_neighbors(s))
                for s in landscape.states
            ),
            start=start,
            goal=goal,
            s_eff_values=s_eff_map,
            goal_reachable=reachable,
        )

    def record_run(
        self,
        trace: Any,       # RunTrace
        controller_config: Dict[str, Any],
    ) -> None:
        """Record a controller run."""
        metrics = trace.metrics()
        goal = controller_config.get("goal", "")
        self.runs.append(RunRecord(
            path=list(trace.path),
            step_count=len(trace.steps),
            goal_reached=goal in trace.path if goal else False,
            total_tension=trace.total_tension,
            hybrid_override_count=metrics.get("hybrid_override_count", 0),
            controller_config=controller_config,
        ))

    def record_evaluation(self, findings: Dict[str, Any]) -> None:
        """Record final evaluation findings."""
        self.evaluation = EvaluationRecord(findings=findings)

    # ── LLM Call Wrapping ────────────────────────────────────────────

    def wrap_call_fn(
        self,
        original_fn: Callable[[str, str, LLMConfig], str],
    ) -> Callable[[str, str, LLMConfig], str]:
        """Wrap an LLM call function to record every call.

        Returns a new function with the same signature that:
        1. Calls the original
        2. Records system prompt, user prompt, response, model, timing
        3. Returns the original response unchanged
        """
        log = self   # capture reference

        def recording_call_fn(
            system: str, user: str, config: LLMConfig,
        ) -> str:
            t0 = datetime.now(timezone.utc)
            response = original_fn(system, user, config)
            t1 = datetime.now(timezone.utc)
            duration_ms = (t1 - t0).total_seconds() * 1000

            log.llm_calls.append(LLMCallRecord(
                system_prompt=system,
                user_prompt=user,
                raw_response=response,
                model=config.model,
                temperature=config.temperature,
                timestamp=t0.isoformat(),
                duration_ms=round(duration_ms, 1),
            ))
            return response

        return recording_call_fn

    # ── Serialization ────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        d: Dict[str, Any] = {"source_id": self.source_id}

        if self.input:
            d["input"] = asdict(self.input)

        if self.llm_calls:
            d["llm_calls"] = [asdict(c) for c in self.llm_calls]

        if self.proposal:
            d["proposal"] = asdict(self.proposal)

        if self.landscape:
            d["landscape"] = asdict(self.landscape)

        if self.runs:
            d["runs"] = [asdict(r) for r in self.runs]

        if self.evaluation:
            d["evaluation"] = asdict(self.evaluation)

        if self.metadata:
            d["metadata"] = self.metadata

        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProvenanceLog":
        """Reconstruct a ProvenanceLog from a dictionary."""
        log = cls(source_id=d.get("source_id", ""))

        if "input" in d:
            log.input = InputRecord(**d["input"])

        if "llm_calls" in d:
            log.llm_calls = [LLMCallRecord(**c) for c in d["llm_calls"]]

        if "proposal" in d:
            log.proposal = ProposalRecord(**d["proposal"])

        if "landscape" in d:
            log.landscape = LandscapeRecord(**d["landscape"])

        if "runs" in d:
            log.runs = [RunRecord(**r) for r in d["runs"]]

        if "evaluation" in d:
            log.evaluation = EvaluationRecord(**d["evaluation"])

        log.metadata = d.get("metadata", {})
        return log

    def save(self, path: str) -> Path:
        """Save the provenance log as JSON.

        Creates parent directories if needed.
        Returns the Path written.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return p

    @classmethod
    def load(cls, path: str) -> "ProvenanceLog":
        """Load a provenance log from JSON."""
        p = Path(path)
        d = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(d)

    # ── Validation ───────────────────────────────────────────────────

    def chain_complete(self) -> bool:
        """Check if all stages of the evidence chain are recorded."""
        return all([
            self.input is not None,
            len(self.llm_calls) > 0,
            self.proposal is not None,
            self.landscape is not None,
            len(self.runs) > 0,
            self.evaluation is not None,
        ])

    def chain_summary(self) -> str:
        """One-line summary of chain completeness."""
        stages = {
            "input": self.input is not None,
            "llm_calls": len(self.llm_calls) > 0,
            "proposal": self.proposal is not None,
            "landscape": self.landscape is not None,
            "runs": len(self.runs) > 0,
            "evaluation": self.evaluation is not None,
        }
        filled = sum(1 for v in stages.values() if v)
        missing = [k for k, v in stages.items() if not v]
        if not missing:
            return f"ProvenanceLog({self.source_id}): 6/6 stages complete"
        return (
            f"ProvenanceLog({self.source_id}): {filled}/6 stages — "
            f"missing: {', '.join(missing)}"
        )
