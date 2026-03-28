"""E₀ Real-World Demo 2: EZB-Zinsentscheidung als Burden-Landscape.

Maps a European Central Bank monetary policy decision process into E₀
structural primitives:

  States  = macroeconomic situations (inflation, recession, growth, …)
  Edges   = policy/economic transitions (rate hike, rate cut, contagion)
  Δ       = magnitude of economic change
  R₀      = resistance (political, institutional, structural)
  S_eff   = structural burden (low → easy path, high → hard path)

Domain contrast vs. Beipackzettel (Domäne 1):

  Beipackzettel:   tree-like, single goal, no loops, ~10 edges
  EZB-Zinspolitik: cyclic, multi-goal, feedback loops, ~18 edges

Key E₀ phenomena to demonstrate:

  1. Gordian topology — Stagflation is a genuine trap: rate hike AND
     rate cut both have high resistance → destructive interference
  2. Multi-goal competition — Preisstabilität AND Wachstum are
     competing objectives (the ECB's dual mandate tension)
  3. Cycle detection — boom-bust cycles: Wachstum → Inflation →
     Zinserhöhung → Rezession → Zinssenkung → Wachstum
  4. Historization effects — repeated cycles should shift resistance
"""

from __future__ import annotations

from e0_controller import (
    Landscape, Session, HybridMode, Outcome, CanonRef,
    E0Envelope, TransportRegime, ExplorationPolicy,
    format_residual_map,
)

# ── EZB Geldpolitik-Landschaft ──────────────────────────────────────────
#
# Encoding: (source, target) → (Δ, R₀, label)
#   Δ  = magnitude of macroeconomic change
#   R₀ = baseline resistance (political, institutional, structural)
#
# Sources:
#   - EZB Monetary Policy Strategy (2021 review)
#   - Standardmakroökonomik (Taylor Rule, Phillips Curve)
#   - Historische EZB-Zinssätze 2011-2025

EZB_EDGES: dict[tuple[str, str], tuple[float, float, str]] = {
    # ── Inflationsbekämpfung (Kernmandat) ──
    ("INFLATION_HOCH",  "ZINS_ERHOEHUNG"):  (0.80, 0.20, "Leitzinsanhebung zur Inflationsbekämpfung"),
    ("ZINS_ERHOEHUNG",  "INFLATION_SINKT"): (0.70, 0.25, "Transmissionsmechanismus: höhere Zinsen dämpfen Nachfrage"),
    ("INFLATION_SINKT", "PREISSTABILITAET"):(0.60, 0.20, "Inflation erreicht Zielband ~2%"),

    # ── Rezessionsrisiko durch Straffung ──
    ("ZINS_ERHOEHUNG",  "REZESSION"):       (0.50, 0.55, "Übermäßige Straffung bremst Wirtschaft"),
    ("REZESSION",       "ARBEITSLOSIGKEIT"):(0.70, 0.30, "Konjunktureinbruch → Beschäftigungsabbau"),
    ("ARBEITSLOSIGKEIT","ZINS_SENKUNG"):    (0.80, 0.20, "Politischer Druck zur Lockerung"),

    # ── Konjunkturbelebung ──
    ("REZESSION",       "ZINS_SENKUNG"):    (0.70, 0.25, "EZB senkt Leitzins zur Konjunkturstützung"),
    ("ZINS_SENKUNG",    "KREDIT_EXPANSION"):(0.60, 0.35, "Günstigere Kredite stimulieren Investition"),
    ("KREDIT_EXPANSION","WACHSTUM"):        (0.50, 0.30, "Multiplikatoreffekt → BIP-Anstieg"),

    # ── Zyklen: Überhitzung und Feedback ──
    ("WACHSTUM",        "INFLATION_HOCH"):  (0.40, 0.55, "Nachfrageüberhang → erneuter Preisdruck"),
    ("WACHSTUM",        "PREISSTABILITAET"):(0.30, 0.20, "Moderates Wachstum bei stabilen Preisen"),
    ("PREISSTABILITAET","WACHSTUM"):        (0.40, 0.25, "Stabile Preise ermöglichen Investition"),

    # ── Stagflation: Gordian Trap ──
    # STAGFLATION is an isolated trap: no incoming edges from the main
    # policy graph.  It exists only as a starting state (scenario 3) to
    # demonstrate the Gordian topology.
    #
    # Design rationale: when REZESSION → STAGFLATION existed, STAGFLATION's
    # 3 exit families (ZINS_ERH, ZINS_SENK, STRUKTURREFORM) created an
    # amplitude mass trap that overwhelmed all direct policy paths via
    # constructive interference.  This is a genuine cross-domain structural
    # phenomenon (also observed in Beipackzettel), but it prevents the
    # controller from navigating the main policy cycle successfully.
    #
    # In a real macroeconomy, stagflation arises from external supply shocks
    # (oil crisis, pandemic), not from normal monetary policy — so modelling
    # it as an external starting condition is economically accurate.
    ("STAGFLATION",     "ZINS_ERHOEHUNG"):  (0.60, 0.75, "Zinserhöhung in Stagflation: politisch extrem schwierig"),
    ("STAGFLATION",     "ZINS_SENKUNG"):    (0.50, 0.80, "Zinssenkung würde Inflation verschärfen"),
    ("STAGFLATION",     "STRUKTURREFORM"):  (0.70, 0.70, "Angebotsseitige Maßnahmen (langfristig)"),

    # ── Auswege aus Stagflation ──
    ("STRUKTURREFORM",  "WACHSTUM"):        (0.60, 0.55, "Strukturmaßnahmen brauchen Zeit, wirken aber nachhaltig"),
}


# ── Landscape-Builder ────────────────────────────────────────────────────

def build_ezb_landscape() -> Landscape:
    """Convert EZB edge table into an E₀ Landscape."""
    L = Landscape()
    for (src, tgt), (delta, resistance, _label) in EZB_EDGES.items():
        L.add_edge(src, tgt, delta=delta, resistance=resistance)
    return L


# ── Execute function ─────────────────────────────────────────────────────

def _always_success(source: str, target: str) -> Outcome:
    """Deterministic execute: every transition succeeds."""
    return Outcome.SUCCESS


# ── Envelopes ────────────────────────────────────────────────────────────

ENVELOPE_INFLATION = E0Envelope(
    mode=HybridMode.AMPLITUDE_ON_DISAGREE,
    geometry="goal_reaching",
    horizon=5,
    transport=TransportRegime.U1,
    goals=frozenset({"PREISSTABILITAET"}),
    alpha=0.5,
)

ENVELOPE_DUAL_MANDATE = E0Envelope(
    mode=HybridMode.AMPLITUDE_ON_DISAGREE,
    geometry="goal_reaching",
    horizon=5,
    transport=TransportRegime.U1,
    goals=frozenset({"WACHSTUM", "PREISSTABILITAET"}),
    alpha=0.5,
)


# ── Scenario runner ──────────────────────────────────────────────────────

def _build_session(
    name: str,
    landscape: Landscape,
    envelope: E0Envelope,
) -> Session:
    """Create a Session with Envelope-based configuration."""
    return Session(
        session_id=f"ezb-{name}",
        landscape=landscape,
        execute_fn=_always_success,
        base_dir="memos/_ezb",
        canon_refs=[CanonRef("e0-canon", "v1", "canon/e0-canon-plain.txt")],
        controller_kwargs={
            **envelope.to_controller_kwargs(),
            "recent_k": 2,
        },
    )


def run_scenario(
    name: str,
    landscape: Landscape,
    start: str,
    goal: str | None = None,
    goals: set[str] | None = None,
    envelope: E0Envelope = ENVELOPE_INFLATION,
    max_cycles: int = 20,
    *,
    hybrid_geometry: str | None = None,
) -> dict:
    """Run one EZB scenario and return structured results.

    Parameters
    ----------
    hybrid_geometry : str, optional
        Legacy shortcut — overrides ``envelope.geometry`` when set.
    """
    if hybrid_geometry is not None:
        envelope = E0Envelope(
            mode=envelope.mode,
            geometry=hybrid_geometry,
            horizon=envelope.horizon,
            transport=envelope.transport,
            goals=(frozenset(goals) if goals
                   else frozenset({goal}) if goal
                   else envelope.goals),
            alpha=envelope.alpha,
        )
    effective_goals = goals or (envelope.goals if envelope.goals else set())
    session = _build_session(name, landscape, envelope)
    result = session.run(
        start,
        goal=goal,
        max_cycles=max_cycles,
        auto_save=False,
    )

    trace = result.trace
    path = trace.path
    overrides = [s for s in trace.steps if s.hybrid_overridden]

    return {
        "name": name,
        "path": path,
        "steps": len(trace.steps),
        "total_tension": trace.total_tension,
        "goals_reached": effective_goals & set(path),
        "goals_missed": effective_goals - set(path),
        "visited_stagflation": "STAGFLATION" in path,
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


def run_iterative_scenario(
    name: str,
    landscape: Landscape,
    start: str,
    goal: str | None = None,
    envelope: E0Envelope = ENVELOPE_INFLATION,
    max_cycles: int = 20,
    max_iterations: int = 5,
    tension_threshold: float = 0.15,
    exploration_policy: ExplorationPolicy | None = None,
) -> dict:
    """Run one EZB scenario through iterate() and return results."""
    effective_goals = envelope.goals if envelope.goals else set()
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
    path = last_trace.path
    overrides = [s for s in last_trace.steps if s.hybrid_overridden]

    return {
        "name": name,
        "path": path,
        "steps": len(last_trace.steps),
        "total_tension": last_trace.total_tension,
        "goals_reached": effective_goals & set(path),
        "goals_missed": effective_goals - set(path),
        "visited_stagflation": "STAGFLATION" in path,
        "hybrid_overrides": len(overrides),
        "override_details": [
            {
                "at": s.source,
                "greedy": s.overlay.deterministic_choice if s.overlay else "?",
                "amplitude": s.target,
            }
            for s in overrides
        ],
        "trace": last_trace,
        "iter_result": iter_result,
    }


# ── Analysis / display ───────────────────────────────────────────────────

def print_result(r: dict) -> None:
    """Pretty-print one scenario result."""
    print(f"\n{'=' * 60}")
    print(f"Szenario: {r['name']}")
    print(f"{'=' * 60}")
    print(f"Pfad:           {' → '.join(r['path'])}")
    print(f"Schritte:       {r['steps']}")
    print(f"Σ S_eff:        {r['total_tension']:.4f}")
    print(f"Ziele erreicht: {r['goals_reached'] or '—'}")
    if r["goals_missed"]:
        print(f"Ziele verfehlt: {r['goals_missed']}")
    if r["visited_stagflation"]:
        print(f"⚠  STAGFLATION besucht")

    print("\nBurden-Profil:")
    for step in r["trace"].steps:
        flag = " ◄ OVERRIDE" if step.hybrid_overridden else ""
        print(f"  {step.source:22s} → {step.target:22s}  "
              f"S_eff={step.s_eff:.4f}{flag}")

    if r["hybrid_overrides"]:
        print(f"\nAmplitude-Overrides: {r['hybrid_overrides']}")
        for od in r["override_details"]:
            print(f"  bei {od['at']}: greedy→{od['greedy']}  "
                  f"amplitude→{od['amplitude']}")


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    print("E₀ Real-World Demo 2: EZB-Zinsentscheidung")
    print("=" * 60)
    print()
    print("Kernfrage: Wie navigiert der E₀-Controller durch")
    print("geldpolitische Zyklen mit konkurrierenden Zielen?")
    print()

    L = build_ezb_landscape()

    # Szenario 1: Inflationsbekämpfung → Preisstabilität
    r1 = run_scenario("inflation_bekaempfung", L,
                      start="INFLATION_HOCH", goal="PREISSTABILITAET",
                      envelope=ENVELOPE_INFLATION)
    print_result(r1)

    # Szenario 2: Rezession → Multi-Goal (Wachstum + Preisstabilität)
    r2 = run_scenario("rezession_multi_goal", L,
                      start="REZESSION", goal="WACHSTUM",
                      envelope=ENVELOPE_DUAL_MANDATE)
    print_result(r2)

    # Szenario 3: Stagflation (Gordian Trap)
    r3 = run_scenario("stagflation_trap", L,
                      start="STAGFLATION", goal="PREISSTABILITAET",
                      envelope=ENVELOPE_INFLATION)
    print_result(r3)

    # Szenario 4: Zyklische Navigation — iterate mit Born-Warmup
    print(f"\n{'=' * 60}")
    print("Szenario 4: Iterativ – Boom-Bust-Zyklus (C41 ExplorationPolicy)")
    print(f"{'=' * 60}")
    policy = ExplorationPolicy.born_warmup(warmup=2, convergence_threshold=0.15)
    print(f"  Envelope: {ENVELOPE_DUAL_MANDATE.summary()}")
    print(f"  Policy:   {policy.label}")
    r4 = run_iterative_scenario(
        "boom_bust_iterativ", L,
        start="INFLATION_HOCH", goal="PREISSTABILITAET",
        envelope=ENVELOPE_DUAL_MANDATE,
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


if __name__ == "__main__":
    main()
