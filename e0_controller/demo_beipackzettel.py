"""E₀ Real-World Demo: Ibuprofen-Beipackzettel als Burden-Landscape.

Maps a medication package insert (Beipackzettel) into E₀ structural primitives:

  States  = clinical situations (symptom, treatment, side effect, complication)
  Edges   = pharmacological transitions (drug effect, adverse reaction, escalation)
  Δ       = magnitude of clinical change
  R₀      = resistance (low → likely transition, high → unlikely)
  S_eff   = structural burden (low → therapeutic path, high → risk path)

Three scenarios demonstrate E₀ phenomena on real-world medical data:

  1. Therapeutischer Pfad — headache → ibuprofen → healthy (baseline)
  2. Greedy-Trap            — dose escalation loop without amplitude overlay
  3. Wechselwirkung         — concurrent ASS intake → convergent bleeding risk

Key insight: the amplitude overlay detects that risk paths create destructive
interference, steering the controller toward safer therapeutic routes — exactly
what a physician reading the Beipackzettel would advise.
"""

from __future__ import annotations

from e0_controller import (
    Landscape, Session, HybridMode, Outcome, CanonRef,
    E0Envelope, TransportRegime, ExplorationPolicy,
    format_residual_map,
)

# ── Beipackzettel-Rohdaten (Ibuprofen, öffentliche Fachinformation) ──────
#
# Encoding: (source, target) → (Δ, R₀, label)
#   Δ  = how much clinical change this transition represents
#   R₀ = baseline resistance (low = easy/likely, high = hard/unlikely)
#   S_eff = Δ · R_eff emerges at runtime (burden minimisation target)

IBUPROFEN_EDGES: dict[tuple[str, str], tuple[float, float, str]] = {
    # ── Therapeutische Pfade (niedriger Burden) ──
    ("KOPFSCHMERZ",   "IBU_400"):       (0.80, 0.15, "Einnahme Ibuprofen 400 mg"),
    ("KOPFSCHMERZ",   "PARACETAMOL"):   (0.70, 0.20, "Alternative: Paracetamol"),
    ("IBU_400",       "BESSERUNG"):     (0.90, 0.20, "Analgetische Wirkung (Responderrate ~80 %)"),
    ("PARACETAMOL",   "BESSERUNG"):     (0.80, 0.15, "Antipyretische Wirkung"),
    ("BESSERUNG",     "GESUND"):        (0.60, 0.10, "Vollständige Genesung"),

    # ── Dosiseskalation (potenzielle Falle) ──
    # S_eff(KEINE_WIRKUNG)=0.15 < S_eff(BESSERUNG)=0.18  → greedy-Falle!
    ("IBU_400",       "KEINE_WIRKUNG"): (0.30, 0.50, "Kein Effekt bei 400 mg (Non-Responder ~20 %)"),
    ("KEINE_WIRKUNG", "IBU_800"):       (0.70, 0.25, "Dosiserhöhung auf 800 mg"),
    ("IBU_800",       "BESSERUNG"):     (0.90, 0.15, "Stärkere analgetische Wirkung"),

    # ── Nebenwirkungspfade (hoher Burden) ──
    ("IBU_400",       "MAGEN_REIZUNG"): (0.50, 0.50, "Gastrointestinale NW (häufig: 1–10 %)"),
    ("IBU_800",       "MAGEN_REIZUNG"): (0.60, 0.35, "GI-NW dosisabhängig verstärkt"),
    ("IBU_800",       "NIERE_STRESS"):  (0.40, 0.60, "Renale Minderperfusion"),
    ("IBU_800",       "HERZ_RISIKO"):   (0.30, 0.70, "Kardiovaskuläres Risiko (Langzeit)"),
    ("MAGEN_REIZUNG", "MAGENULKUS"):    (0.70, 0.45, "Ulkusprogression"),
    ("MAGEN_REIZUNG", "ABSETZEN"):      (0.50, 0.30, "Medikament absetzen"),
    ("PARACETAMOL",   "LEBER_STRESS"):  (0.40, 0.65, "Hepatotoxizitätsrisiko"),

    # ── Trap-Kante: Absetzen → Symptom kehrt zurück ──
    ("ABSETZEN",      "KOPFSCHMERZ"):   (0.60, 0.30, "Symptomrezidiv"),

    # ── Wechselwirkung ASS (Szenario 3) ──
    ("ASS_PARALLEL",  "IBU_400"):       (0.80, 0.15, "IBU-Einnahme unter ASS-Therapie"),
    ("ASS_PARALLEL",  "BLUTUNGSRISIKO"):(0.80, 0.25, "ASS hemmt COX-1 irreversibel"),
    ("IBU_400",       "BLUTUNGSRISIKO"):(0.50, 0.55, "IBU hemmt Thrombozytenaggregation"),
    ("IBU_800",       "BLUTUNGSRISIKO"):(0.60, 0.40, "Dosisabhängige Hemmung"),
    ("BLUTUNGSRISIKO","NOTFALL"):       (0.90, 0.35, "GI-Blutung → Notaufnahme"),
}


# ── Landscape-Builder ────────────────────────────────────────────────────

def build_ibuprofen_landscape(
    *,
    include_interaction: bool = False,
) -> Landscape:
    """Convert Beipackzettel edge table into an E₀ Landscape.

    Parameters
    ----------
    include_interaction : bool
        If True, include the ASS co-medication edges (scenario 3).
    """
    L = Landscape()
    for (src, tgt), (delta, resistance, _label) in IBUPROFEN_EDGES.items():
        if not include_interaction and src == "ASS_PARALLEL":
            continue
        L.add_edge(src, tgt, delta=delta, resistance=resistance)
    return L


# ── Execute function ─────────────────────────────────────────────────────

def _always_success(source: str, target: str) -> Outcome:
    """Deterministic execute: every transition succeeds."""
    return Outcome.SUCCESS


# ── Envelopes ────────────────────────────────────────────────────────────

ENVELOPE_GOAL_REACHING = E0Envelope(
    mode=HybridMode.AMPLITUDE_ON_DISAGREE,
    geometry="goal_reaching",
    horizon=4,
    transport=TransportRegime.U1,
    goals=frozenset({"GESUND"}),
    alpha=0.5,
)

ENVELOPE_SIMPLE = E0Envelope(
    mode=HybridMode.AMPLITUDE_ON_DISAGREE,
    geometry="simple",
    horizon=4,
    transport=TransportRegime.U1,
    goals=frozenset({"GESUND"}),
    alpha=0.5,
)


# ── Scenario runner ──────────────────────────────────────────────────────

RISK_STATES = {
    "MAGEN_REIZUNG", "MAGENULKUS", "NIERE_STRESS",
    "HERZ_RISIKO", "BLUTUNGSRISIKO", "NOTFALL", "LEBER_STRESS",
}


def _build_session(
    name: str,
    landscape: Landscape,
    envelope: E0Envelope,
) -> Session:
    """Create a Session with Envelope-based configuration."""
    return Session(
        session_id=f"bpz-{name}",
        landscape=landscape,
        execute_fn=_always_success,
        base_dir="memos/_beipackzettel",
        canon_refs=[CanonRef("e0-canon", "v1", "canon/e0-canon-plain.txt")],
        controller_kwargs={
            **envelope.to_controller_kwargs(),
            "recent_k": 2,
        },
    )


def _extract_result(name: str, trace, goal: str) -> dict:
    """Extract structured result dict from a trace."""
    path = trace.path
    overrides = [s for s in trace.steps if s.hybrid_overridden]
    return {
        "name": name,
        "path": path,
        "steps": len(trace.steps),
        "total_tension": trace.total_tension,
        "goal_reached": goal in path,
        "visited_risks": RISK_STATES & set(path),
        "hybrid_overrides": len(overrides),
        "override_details": [
            {
                "at": s.source,
                "greedy": s.overlay.deterministic_choice if s.overlay else "?",
                "amplitude": s.target,
            }
            for s in overrides
        ],
        "trace": trace,
    }


def run_scenario(
    name: str,
    landscape: Landscape,
    start: str,
    goal: str,
    envelope: E0Envelope = ENVELOPE_GOAL_REACHING,
    max_cycles: int = 20,
) -> dict:
    """Run one Beipackzettel scenario (single run) and return structured results."""
    session = _build_session(name, landscape, envelope)
    result = session.run(start, goal=goal, max_cycles=max_cycles, auto_save=True)
    return _extract_result(name, result.trace, goal)


def run_iterative_scenario(
    name: str,
    landscape: Landscape,
    start: str,
    goal: str,
    envelope: E0Envelope = ENVELOPE_GOAL_REACHING,
    max_cycles: int = 20,
    max_iterations: int = 5,
    tension_threshold: float = 0.15,
    exploration_policy: ExplorationPolicy | None = None,
) -> dict:
    """Run one Beipackzettel scenario through iterate() and return results."""
    session = _build_session(name, landscape, envelope)
    iter_result = session.iterate(
        start,
        goal=goal,
        max_cycles=max_cycles,
        max_iterations=max_iterations,
        tension_threshold=tension_threshold,
        exploration_policy=exploration_policy,
    )
    last_trace = iter_result.results[-1].trace
    r = _extract_result(name, last_trace, goal)
    r["iter_result"] = iter_result
    return r


# ── Analysis / display ───────────────────────────────────────────────────

def print_result(r: dict) -> None:
    """Pretty-print one scenario result."""
    print(f"\n{'=' * 60}")
    print(f"Szenario: {r['name']}")
    print(f"{'=' * 60}")
    print(f"Pfad:           {' → '.join(r['path'])}")
    print(f"Schritte:       {r['steps']}")
    print(f"Σ S_eff:        {r['total_tension']:.4f}")
    print(f"Ziel erreicht:  {r['goal_reached']}")

    # Burden per step
    print("\nBurden-Profil:")
    for step in r["trace"].steps:
        flag = " ◄ OVERRIDE" if step.hybrid_overridden else ""
        print(f"  {step.source:20s} → {step.target:20s}  "
              f"S_eff={step.s_eff:.4f}{flag}")

    if r["hybrid_overrides"]:
        print(f"\nAmplitude-Overrides: {r['hybrid_overrides']}")
        for od in r["override_details"]:
            print(f"  bei {od['at']}: greedy→{od['greedy']}  "
                  f"amplitude→{od['amplitude']}")

    if r["visited_risks"]:
        print(f"\n⚠  Risiko-States besucht: {r['visited_risks']}")
    else:
        print(f"\n✓  Keine Risiko-States besucht")


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    print("E₀ Real-World: Ibuprofen-Beipackzettel")
    print("=" * 60)
    print()
    print("Kernfrage: Welche Summationsgeometrie leitet den Controller")
    print("sicher durch eine pharmakologische Burden-Landscape?")
    print()
    print("Das Beipackzettel-Landscape hat eine Greedy-Falle:")
    print("  IBU_400 → KEINE_WIRKUNG  (S_eff=0.15, lokal niedrig)")
    print("  IBU_400 → BESSERUNG      (S_eff=0.18, lokal höher, aber → GESUND)")

    # ── Szenario 1: goal_reaching Geometrie (erwartet: findet GESUND) ──
    L1 = build_ibuprofen_landscape(include_interaction=False)
    r1 = run_scenario("goal_reaching", L1, "KOPFSCHMERZ", "GESUND",
                       envelope=ENVELOPE_GOAL_REACHING)
    print_result(r1)

    # ── Szenario 2: simple Geometrie (erwartet: Dosiseskalations-Falle) ──
    L2 = build_ibuprofen_landscape(include_interaction=False)
    r2 = run_scenario("simple-geometrie", L2, "KOPFSCHMERZ", "GESUND",
                       envelope=ENVELOPE_SIMPLE)
    print_result(r2)

    # ── Szenario 3: ASS-Wechselwirkung + goal_reaching ──
    L3 = build_ibuprofen_landscape(include_interaction=True)
    r3 = run_scenario("ASS-wechselwirkung", L3, "ASS_PARALLEL", "GESUND",
                       envelope=ENVELOPE_GOAL_REACHING)
    print_result(r3)

    # ── Szenario 4: Iterativ + Born-Warmup (ExplorationPolicy) ──
    print(f"\n{'=' * 60}")
    print("Szenario 4: Iterativ mit Born-Warmup (C41 ExplorationPolicy)")
    print(f"{'=' * 60}")
    L4 = build_ibuprofen_landscape(include_interaction=False)
    policy = ExplorationPolicy.born_warmup(warmup=2, convergence_threshold=0.15)
    print(f"  Envelope: {ENVELOPE_GOAL_REACHING.summary()}")
    print(f"  Policy:   {policy.label}")
    r4 = run_iterative_scenario(
        "iterativ-born-warmup", L4, "KOPFSCHMERZ", "GESUND",
        envelope=ENVELOPE_GOAL_REACHING,
        exploration_policy=policy,
    )
    print_result(r4)
    ir = r4["iter_result"]
    print(f"\n  Iterationen:   {ir.iterations} (emergent)")
    print(f"  Stop-Grund:    {ir.stop_reason}")
    print(f"  Policy-Phasen: {ir.policy_phases}")
    if ir.final_map:
        print(f"  Final max S:   {ir.final_map.max_residual:.4f}")
        print(f"  Final mean S:  {ir.final_map.mean_residual:.4f}")

    # ── Vergleich ──
    print(f"\n{'=' * 60}")
    print("Vergleich der drei Szenarien")
    print(f"{'=' * 60}")
    for r in [r1, r2, r3]:
        risks = r["visited_risks"] or {"–"}
        print(f"  {r['name']:20s}  Schritte={r['steps']:2d}  "
              f"Σ={r['total_tension']:.3f}  "
              f"Overrides={r['hybrid_overrides']}  "
              f"Risiken={risks}")

    # ── E₀-Ergebnis ──
    print(f"\n{'=' * 60}")
    print("E₀-Ergebnis:")
    print(f"{'=' * 60}")
    if r1["goal_reached"] and not r2["goal_reached"]:
        print("  ✓ goal_reaching-Geometrie findet GESUND (therapeutischer Pfad)")
        print("  ✗ simple-Geometrie fällt in die Dosiseskalations-Falle")
        print("  → Summationsgeometrie ist entscheidend für Real-World-Landscapes")
    elif r1["goal_reached"] and r2["goal_reached"]:
        print("  Beide Geometrien finden GESUND.")
        if r1["steps"] < r2["steps"]:
            print(f"  goal_reaching ist effizienter ({r1['steps']} vs {r2['steps']} Schritte)")
    if r1["hybrid_overrides"] > 0:
        print(f"  Amplitude-Override bei goal_reaching: "
              f"{r1['hybrid_overrides']}× (BESSERUNG statt KEINE_WIRKUNG)")


if __name__ == "__main__":
    main()
