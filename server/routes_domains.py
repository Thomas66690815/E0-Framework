"""REST routes for E₀ Domain Studio (ARC-K, C307).

Human-initiated Learn/Apply workflow via REST API.

Endpoints
---------
POST   /domains                       Create domain workspace
GET    /domains                       List all domains
GET    /domains/{name}                Status
POST   /domains/{name}/upload         File upload → inject (multipart)
POST   /domains/{name}/learn          Run N learning episodes
PUT    /domains/{name}/mode           Switch mode (learn/apply/hybrid)
POST   /domains/{name}/recommend      Recommend next state
POST   /domains/{name}/record         Manual inscription
DELETE /domains/{name}                Delete domain
GET    /domains/{name}/conviction     Conviction map

Oracle types (for /learn)
--------------------------
always_success   — every step is SUCCESS (useful for topology exploration)
random           — random SUCCESS / FAILURE (50 / 50)
topology_aware   — SUCCESS on edges that exist with U > F, else FAILURE
goal_aware       — SUCCESS if the step strictly decreases BFS distance to goal
                   (requires goal to be set in the request)
llm              — asks the OpenAI API to judge each transition;
                   requires OPENAI_API_KEY in .env or environment;
                   gracefully falls back to FAILURE on API/parse errors

C307.
"""

from __future__ import annotations

import random as _random
from collections import deque
from typing import Callable, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File

from e0_controller.domain_session import DomainMode, DomainSession, DomainStore
from e0_controller.primitives import Edge, Outcome

from server.models import (
    ConvictionMapResponse,
    CreateDomainRequest,
    DomainListItem,
    DomainStatusResponse,
    InjectResponse,
    LearnRequest,
    LearnResponse,
    RecommendRequest,
    RecommendResponse,
    RecordRequest,
    RecordResponse,
    SetModeRequest,
)

router = APIRouter(prefix="/domains", tags=["domains"])

# ── Module-level store (injected for tests via set_store()) ──────────────────

_store: Optional[DomainStore] = None


def set_store(store: DomainStore) -> None:
    global _store
    _store = store


def _get_store() -> DomainStore:
    global _store
    if _store is None:
        _store = DomainStore()
    return _store


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_or_404(name: str) -> DomainSession:
    session = _get_store().load(name)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Domain {name!r} not found")
    return session


def _save(session: DomainSession) -> None:
    _get_store().save(session)


def _status_response(session: DomainSession) -> DomainStatusResponse:
    st = session.status()
    return DomainStatusResponse(
        name=st["name"],
        description=st.get("description", ""),
        topic=st.get("topic", ""),
        mode=st["mode"],
        episode_count=st["episode_count"],
        states=st["states"],
        edges=st["edges"],
        total_inscriptions=st["total_inscriptions"],
        cold_start=st["cold_start"],
        created_at=st["created_at"],
    )


def _bfs_distances_to_goal(landscape, goal: str) -> dict:
    """Reverse-BFS distances from every node to *goal* in the directed landscape.

    Returns a dict {node: distance}.  Nodes unreachable from *goal* (via reversed
    edges) are absent from the dict (effectively distance = infinity).
    """
    # Build reverse adjacency list (target → list of sources)
    reverse_adj: dict = {}
    for e in landscape.edges:
        reverse_adj.setdefault(e.target, []).append(e.source)

    dist = {goal: 0}
    queue = deque([goal])
    while queue:
        node = queue.popleft()
        for pred in reverse_adj.get(node, []):
            if pred not in dist:
                dist[pred] = dist[node] + 1
                queue.append(pred)
    return dist


def _llm_oracle(session: "DomainSession", call_fn=None) -> Callable[[str, str], Outcome]:
    """Return an oracle that calls OpenAI to judge each (source, target) transition.

    Requires OPENAI_API_KEY in .env or environment.  On any error (API,
    missing key, unparseable response) the transition is scored as FAILURE.

    *call_fn* is injectable for tests: signature (system, user, config) -> str.
    """
    from e0_controller.llm_adapter import LLMConfig, openai_call

    config = LLMConfig(temperature=0.0, max_tokens=10)
    _call = call_fn or openai_call

    topic = session.topic or session.name
    description = session.description or ""
    system_msg = (
        "You evaluate single transitions in a domain workflow. "
        "Reply with exactly one word: SUCCESS, FAILURE, or PARTIAL."
    )

    def oracle(s: str, t: str) -> Outcome:
        user_msg = (
            f"Domain: {topic}. {description}\n"
            f"Transition: {s!r} → {t!r}\n"
            "Is this a successful step? Reply SUCCESS, FAILURE, or PARTIAL."
        )
        try:
            raw = _call(system_msg, user_msg, config).strip().upper()
        except Exception:
            return Outcome.FAILURE

        if "PARTIAL" in raw:
            return Outcome.PARTIAL
        if "SUCCESS" in raw:
            return Outcome.SUCCESS
        return Outcome.FAILURE

    return oracle


def _oracle_for(
    oracle_type: str,
    landscape,
    goal: Optional[str] = None,
    session=None,
    llm_call_fn=None,
) -> Callable[[str, str], Outcome]:
    """Return a callable oracle for the given type string."""
    if oracle_type == "always_success":
        return lambda s, t: Outcome.SUCCESS

    if oracle_type == "random":
        def _random_oracle(s: str, t: str) -> Outcome:
            return _random.choice([Outcome.SUCCESS, Outcome.FAILURE])
        return _random_oracle

    if oracle_type == "topology_aware":
        def _topo_oracle(s: str, t: str) -> Outcome:
            e = Edge(s, t)
            h = landscape.historization
            u = h._U.get(e, 0.0)
            f = h._F.get(e, 0.0)
            return Outcome.SUCCESS if u >= f else Outcome.FAILURE
        return _topo_oracle

    if oracle_type == "goal_aware":
        # goal is validated non-None in the route handler before reaching here
        dist = _bfs_distances_to_goal(landscape, goal)  # type: ignore[arg-type]
        def _goal_oracle(s: str, t: str) -> Outcome:
            d_s = dist.get(s, float("inf"))
            d_t = dist.get(t, float("inf"))
            return Outcome.SUCCESS if d_t < d_s else Outcome.FAILURE
        return _goal_oracle

    if oracle_type == "llm":
        return _llm_oracle(session, call_fn=llm_call_fn)

    # Fallback (should be caught by Pydantic pattern validation)
    return lambda s, t: Outcome.SUCCESS


def _pick_start(session: DomainSession, requested: Optional[str]) -> str:
    """Return the requested start state or the first state in the landscape."""
    states = list(session.landscape.states)
    if not states:
        return requested or "START"
    if requested and requested in session.landscape.states:
        return requested
    # Use first state as default
    return next(iter(session.landscape.states))


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("", status_code=201, response_model=DomainStatusResponse)
def create_domain(req: CreateDomainRequest):
    """Create a new named domain workspace."""
    store = _get_store()
    if store.exists(req.name):
        raise HTTPException(status_code=409, detail=f"Domain {req.name!r} already exists")
    session = DomainSession(
        name=req.name,
        description=req.description,
        topic=req.topic,
        mode=DomainMode(req.mode),
    )
    store.save(session)
    return _status_response(session)


@router.get("", response_model=List[DomainListItem])
def list_domains():
    """List all persisted domain workspaces."""
    return [DomainListItem(name=n) for n in _get_store().list_domains()]


@router.get("/{name}", response_model=DomainStatusResponse)
def get_domain(name: str):
    """Get domain status."""
    return _status_response(_load_or_404(name))


@router.delete("/{name}", status_code=204)
def delete_domain(name: str):
    """Delete a domain workspace."""
    if not _get_store().delete(name):
        raise HTTPException(status_code=404, detail=f"Domain {name!r} not found")


@router.post("/{name}/upload", response_model=InjectResponse)
async def upload_file(name: str, file: UploadFile = File(...)):
    """Upload a CSV, JSON, or text file and inject it into the domain landscape.

    The file type is auto-detected from the filename extension:
    - .csv  → CSV injection (source, target [, outcome])
    - .json → JSON injection (edge list or DomainSpec)
    - .txt  → text injection (LLM-backed bootstrapper if available)
    """
    session = _load_or_404(name)

    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")

    # Determine hint from filename
    filename = (file.filename or "").lower()
    if filename.endswith(".json"):
        hint = "json"
    elif filename.endswith(".txt"):
        hint = "text"
    else:
        hint = "csv"  # default, also handles .csv

    report = session.inject(content_bytes, hint=hint)
    _save(session)

    return InjectResponse(
        edges_added=report.edges_added,
        inscriptions=report.inscriptions,
        skipped=report.skipped,
        warnings=report.warnings,
    )


@router.post("/{name}/learn", response_model=LearnResponse)
def learn(name: str, req: LearnRequest):
    """Run N learning episodes using HistorizedQuantumWalk."""
    session = _load_or_404(name)

    if req.oracle_type == "goal_aware" and not req.goal:
        raise HTTPException(
            status_code=422,
            detail="oracle_type='goal_aware' requires a 'goal' state to be set.",
        )

    start = _pick_start(session, req.start)
    oracle = _oracle_for(
        req.oracle_type,
        session.landscape,
        goal=req.goal,
        session=session,
    )

    report = session.learn(
        oracle_fn=oracle,
        n_episodes=req.n_episodes,
        start=start,
        goal=req.goal,
        max_steps=req.max_steps,
    )
    _save(session)

    return LearnResponse(
        episodes=report.episodes,
        total_steps=report.total_steps,
        success_count=report.success_count,
        failure_count=report.failure_count,
        partial_count=report.partial_count,
        edges_explored=report.edges_explored,
        goal_rate=report.goal_rate,
        warnings=report.warnings,
    )


@router.put("/{name}/mode", response_model=DomainStatusResponse)
def set_mode(name: str, req: SetModeRequest):
    """Switch the domain mode (learn / apply / hybrid)."""
    session = _load_or_404(name)
    session.set_mode(DomainMode(req.mode))
    _save(session)
    return _status_response(session)


@router.post("/{name}/recommend", response_model=RecommendResponse)
def recommend(name: str, req: RecommendRequest):
    """Recommend the best next state from a list of candidates."""
    session = _load_or_404(name)
    result = session.recommend(req.state, req.candidates)
    _save(session)  # auto-created edges are persisted

    return RecommendResponse(
        recommended=result.recommended,
        reason=result.reason,
        quality=result.quality,
        conviction_score=result.conviction_score,
        candidates=result.candidates,
        cold_start=result.cold_start,
    )


@router.post("/{name}/record", response_model=RecordResponse)
def record(name: str, req: RecordRequest):
    """Manually inscribe an edge outcome into the domain landscape."""
    session = _load_or_404(name)
    ok = session.record(req.source, req.target, req.outcome)
    if ok:
        _save(session)
        return RecordResponse(ok=True,
                              message=f"Inscribed {req.source}→{req.target} as {req.outcome}")
    return RecordResponse(ok=False,
                          message=f"Unknown outcome {req.outcome!r}. "
                                  f"Use: success / failure / partial")


@router.get("/{name}/conviction", response_model=ConvictionMapResponse)
def conviction_map(name: str):
    """Return conviction scores for all edges in the domain."""
    session = _load_or_404(name)
    return ConvictionMapResponse(edges=session.conviction_map())
