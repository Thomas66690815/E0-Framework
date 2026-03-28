"""E₀ Real-World Demo 3: Burnout — Composite Multi-Perspective Memo.

First non-synthetic domain: the user provides raw text fragments
from multiple perspectives, the LLM generates the landscape, and the
controller navigates it.  Neither user nor developer pre-designed the
topology — this is the anti-circularity test.

Ingress data (5 fragments, all German):
  1. Arbeitsmarkt / ökonomisch — stress statistics, productivity vs health
  2. Psychologisch — bidirectional stress↔burnout feedback loop
  3. Journalismus — sector-specific identity fusion with work
  4. Erfahrungsbericht — first-person, gradual erosion
  5. Autofiktional — gradual loss of connectivity, delayed recognition

Key E₀ phenomena expected:
  - Mass trap candidate: stress↔burnout feedback loop (Fragment 2)
  - Non-linear phase transition: gradual erosion → sudden loss (Fragment 4/5)
  - Multi-perspective interference: different frames produce different paths
  - Amplitude may reveal hidden structure that greedy misses

Usage:
    # Live LLM (requires OPENAI_API_KEY in .env):
    py -3 -m e0_controller.demo_burnout_composite

    # Mock mode (no API key needed):
    py -3 -m e0_controller.demo_burnout_composite --mock

    # Hybrid amplitude mode:
    py -3 -m e0_controller.demo_burnout_composite --hybrid
"""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

from e0_controller import (
    Landscape,
    Session,
    HybridMode,
    Outcome,
    CanonRef,
    E0Envelope,
    TransportRegime,
    E0LLMAdapter,
    LLMConfig,
    LandscapeProposal,
    materialize_landscape,
    task_map_from_proposal,
    graph_quality,
    evaluate_run,
    ScenarioEvaluation,
    should_reflect,
    reflect,
    format_reflection_report,
)
from e0_controller.amplitude_overlay import OverlayReport


# ── Burnout Text Fragments ───────────────────────────────────────────────
#
# Real-world ingress: 5 perspectives on Burnout, provided as-is.
# These go through E0LLMAdapter.build_landscape() — we do NOT
# pre-design the state graph.

FRAGMENT_OEKONOMISCH = """\
Laut einer Studie der Techniker Krankenkasse aus dem Jahr 2023 \
haben sich die Fehltage aufgrund psychischer Belastungen in \
Deutschland in den letzten zehn Jahren um über 20 Prozent erhöht. \
Dabei entfallen auf Burnout-bezogene Diagnosen durchschnittlich \
rund 30 Krankheitstage pro Fall — deutlich mehr als bei den meisten \
somatischen Erkrankungen.

Die ökonomischen Kosten sind erheblich: Unternehmen verlieren \
nicht nur Produktivität, sondern auch qualifiziertes Personal, \
wenn Betroffene langfristig ausfallen oder den Beruf wechseln. \
Gleichzeitig entsteht ein struktureller Konflikt: Die Maßnahmen, \
die kurzfristig die Produktivität steigern (höhere Arbeitsdichte, \
Erreichbarkeit, Flexibilisierung), sind häufig genau jene, die \
langfristig die psychische Gesundheit gefährden.

Zwischen Produktivitätssteigerung und Gesundheitsschutz besteht \
also ein realer Zielkonflikt — und dieser reproduziert sich auf \
jeder Organisationsebene: im Team, in der Abteilung, im Unternehmen.\
"""

FRAGMENT_PSYCHOLOGISCH = """\
In der psychologischen Fachliteratur wird Burnout als Zustand \
emotionaler Erschöpfung, Depersonalisation und reduzierter \
persönlicher Leistungsfähigkeit beschrieben (Maslach & Leiter, 2016).

Entscheidend ist die bidirektionale Dynamik: Stress führt zu \
Erschöpfung, Erschöpfung senkt die wahrgenommene Kontrolle, \
reduzierte Kontrolle verstärkt den Stress. Es entsteht ein \
Rückkopplungskreislauf, der sich ohne äußere Intervention \
nicht selbst stabilisiert.

Hinzu kommt: Die Entwicklung verläuft nicht linear. In frühen \
Phasen kann die Person noch kompensieren — oft sogar mit \
gesteigerter Leistung. Der Übergang in die dekompensierte Phase \
ist häufig abrupt und für Betroffene selbst schwer zu erkennen.

Nicht die Belastung allein ist entscheidend, sondern das Verhältnis \
von Anforderung und wahrgenommener Kontrolle.\
"""

FRAGMENT_JOURNALISMUS = """\
Im Journalismus zeigen Studien, dass rund 45 Prozent der Befragten \
über Burnout-Symptome berichten (Reuters Digital News Report, 2022).

Besonderheit: Im Journalismus verschmilzt berufliche Identität \
häufig mit Selbstwert. Die Arbeit wird nicht als austauschbar \
erlebt, sondern als konstitutiv für das Selbstbild. Die Folge: \
Abgrenzung wird als Identitätsverlust wahrgenommen.

Die Kombination aus permanenter Erreichbarkeit, zeitkritischen \
Deadlines und emotionaler Exposition gegenüber belastenden \
Inhalten erzeugt ein spezifisches Risikoprofil — und gleichzeitig \
ein erschwertes Hilfe-Suchen, weil professionelle Belastbarkeit \
als Kernkompetenz gilt.\
"""

FRAGMENT_ERFAHRUNGSBERICHT = """\
Ich habe nicht plötzlich aufgehört zu funktionieren. Es war kein \
einzelner Moment. Eher eine langsame Verschiebung:

Zuerst wurde die Erholung kürzer. Dann ineffektiver. Irgendwann \
hat sie gar nicht mehr stattgefunden.

Ich habe trotzdem weitergearbeitet. Nicht aus Pflichtgefühl, \
sondern weil ich nicht wusste, was ich stattdessen tun sollte.

Der schlimmste Moment war nicht der Zusammenbruch — sondern die \
Erkenntnis: Ich saß vor einer einfachen Aufgabe und konnte sie \
nicht mehr lösen. Nicht, weil sie schwer war. Sondern weil keine \
Verbindung mehr da war.\
"""

FRAGMENT_AUTOFIKTIONAL = """\
Ich habe nicht gemerkt, dass ich erschöpft war.
Erschöpfung fühlt sich anders an.

Es war eher so, dass Dinge nicht mehr verbunden waren.
Aufgaben waren noch da, aber sie griffen nicht mehr ineinander.

Ich konnte arbeiten.
Aber es führte zu nichts.

Am Anfang habe ich das als Disziplinproblem interpretiert.
Mehr Fokus. Mehr Kontrolle. Mehr Struktur.

Das hat alles kurzfristig funktioniert.
Und gleichzeitig etwas weiter destabilisiert, ohne dass ich es sehen konnte.

Der eigentliche Bruch war nicht spektakulär.
Kein Zusammenbruch. Kein Moment.

Sondern eine einfache Feststellung:

Ich sitze vor einer Aufgabe
und es gibt keinen Zugriff mehr darauf.

Nicht, weil ich sie nicht verstehe.
Sondern weil keine Verbindung mehr entsteht.

Ab da lief alles weiter.
Aber ohne Rückkopplung.

Und genau das ist schwer zu erkennen:
Nach außen sieht es identisch aus.\
"""


ALL_FRAGMENTS = {
    "oekonomisch": FRAGMENT_OEKONOMISCH,
    "psychologisch": FRAGMENT_PSYCHOLOGISCH,
    "journalismus": FRAGMENT_JOURNALISMUS,
    "erfahrungsbericht": FRAGMENT_ERFAHRUNGSBERICHT,
    "autofiktional": FRAGMENT_AUTOFIKTIONAL,
}


def composite_source_text() -> str:
    """Assemble all fragments into a single source text block."""
    parts = []
    for label, text in ALL_FRAGMENTS.items():
        parts.append(f"── Perspektive: {label} ──\n{text}")
    return "\n\n".join(parts)


# ── Task description for LLM ────────────────────────────────────────────

BURNOUT_TASK = (
    "Erstelle ein strukturiertes Burnout-Memo auf Basis der fünf "
    "Quellenperspektiven (ökonomisch, psychologisch, journalistisch, "
    "Erfahrungsbericht, autofiktional). Das Memo soll:\n"
    "1. Die Kernmechanismen identifizieren (Rückkopplung, Phasen, Bruchpunkt)\n"
    "2. Die Perspektiven gegeneinander stellen (Gemeinsamkeiten, Widersprüche)\n"
    "3. Strukturelle Muster herausarbeiten (wo greifen die Beschreibungen ineinander?)\n"
    "4. Offene Fragen benennen (was fehlt, was widerspricht sich?)\n\n"
    "Source material:\n"
)

DEFAULT_START = "RAW_FRAGMENTS"
DEFAULT_GOAL = "MEMO_COMPLETE"


# ── Mock LLM for --mock mode ────────────────────────────────────────────

def mock_llm_call(system: str, user: str, config: LLMConfig) -> str:
    """Deterministic mock for burnout-composite demo.

    Models the expected structure: 5 fragments → synthesis stages →
    integration → memo.  Includes a feedback-loop recovery path
    (the mass trap candidate from Fragment 2).
    """
    if "design the complete state graph" in user:
        return json.dumps({
            "states": [
                # Ingress
                "RAW_FRAGMENTS",
                "PERSPECTIVES_PARSED",
                # Analysis
                "MECHANISMS_IDENTIFIED",
                "FEEDBACK_LOOP_DETECTED",
                "PHASE_MODEL_BUILT",
                # Synthesis
                "CROSS_PERSPECTIVE_COMPARED",
                "CONTRADICTIONS_MAPPED",
                "STRUCTURAL_PATTERNS_EXTRACTED",
                # Output
                "OPEN_QUESTIONS_FORMULATED",
                "MEMO_ASSEMBLED",
                "MEMO_COMPLETE",
                # Recovery / trap paths
                "LOOP_UNRESOLVED",
                "REFRAMING_NEEDED",
            ],
            "edges": [
                # Happy path
                {"source": "RAW_FRAGMENTS", "target": "PERSPECTIVES_PARSED",
                 "delta": 0.3, "resistance": 0.4,
                 "description": "Parse and segment the five source perspectives."},
                {"source": "PERSPECTIVES_PARSED", "target": "MECHANISMS_IDENTIFIED",
                 "delta": 0.5, "resistance": 0.7,
                 "description": "Extract core mechanisms from each perspective."},
                {"source": "MECHANISMS_IDENTIFIED", "target": "FEEDBACK_LOOP_DETECTED",
                 "delta": 0.4, "resistance": 0.6,
                 "description": "Identify the bidirectional stress-burnout feedback loop."},
                {"source": "FEEDBACK_LOOP_DETECTED", "target": "PHASE_MODEL_BUILT",
                 "delta": 0.5, "resistance": 0.8,
                 "description": "Build phase model: compensation → decompensation → break."},
                {"source": "PHASE_MODEL_BUILT", "target": "CROSS_PERSPECTIVE_COMPARED",
                 "delta": 0.4, "resistance": 0.6,
                 "description": "Compare perspectives: where do they agree/diverge?"},
                {"source": "CROSS_PERSPECTIVE_COMPARED", "target": "CONTRADICTIONS_MAPPED",
                 "delta": 0.3, "resistance": 0.5,
                 "description": "Map contradictions between economic and psychological framing."},
                {"source": "CONTRADICTIONS_MAPPED", "target": "STRUCTURAL_PATTERNS_EXTRACTED",
                 "delta": 0.4, "resistance": 0.7,
                 "description": "Extract structural patterns across all five perspectives."},
                {"source": "STRUCTURAL_PATTERNS_EXTRACTED", "target": "OPEN_QUESTIONS_FORMULATED",
                 "delta": 0.3, "resistance": 0.5,
                 "description": "Formulate open questions and gaps in the analysis."},
                {"source": "OPEN_QUESTIONS_FORMULATED", "target": "MEMO_ASSEMBLED",
                 "delta": 0.3, "resistance": 0.4,
                 "description": "Assemble all sections into structured burnout memo."},
                {"source": "MEMO_ASSEMBLED", "target": "MEMO_COMPLETE",
                 "delta": 0.1, "resistance": 0.2,
                 "description": "Final review and completion."},
                # Feedback-loop trap path (mass trap candidate)
                {"source": "FEEDBACK_LOOP_DETECTED", "target": "LOOP_UNRESOLVED",
                 "delta": 0.3, "resistance": 1.2,
                 "description": "Feedback loop is self-reinforcing, cannot be cleanly decomposed."},
                {"source": "LOOP_UNRESOLVED", "target": "REFRAMING_NEEDED",
                 "delta": 0.4, "resistance": 1.5,
                 "description": "Need to reframe: loop is not a bug but the core structure."},
                {"source": "REFRAMING_NEEDED", "target": "PHASE_MODEL_BUILT",
                 "delta": 0.5, "resistance": 0.9,
                 "description": "Reframing allows loop integration into phase model."},
                # Direct recovery from unresolved loop
                {"source": "LOOP_UNRESOLVED", "target": "PHASE_MODEL_BUILT",
                 "delta": 0.4, "resistance": 1.1,
                 "description": "Accept loop as irreducible, proceed with partial model."},
            ],
        })

    if "Execute the transition" in user:
        return json.dumps({
            "outcome": "SUCCESS",
            "result": "Transition completed based on source material analysis.",
            "confidence": 0.82,
        })

    return json.dumps({
        "delta": 0.4,
        "reasoning": "Moderate structural change in burnout analysis.",
    })


# ── Envelope presets ─────────────────────────────────────────────────────

ENVELOPE_GREEDY = E0Envelope(
    mode=HybridMode.GREEDY,
    geometry="simple",
    horizon=3,
    transport=TransportRegime.U1,
    goals=frozenset({DEFAULT_GOAL}),
    alpha=2.0,
)

ENVELOPE_HYBRID = E0Envelope(
    mode=HybridMode.AMPLITUDE_ON_DISAGREE,
    geometry="goal_reaching",
    horizon=5,
    transport=TransportRegime.U1,
    goals=frozenset({DEFAULT_GOAL}),
    alpha=0.5,
)


# ── Main demo ────────────────────────────────────────────────────────────

def run_demo(
    use_mock: bool = False,
    use_hybrid: bool = False,
    envelope: Optional[E0Envelope] = None,
) -> dict:
    """Run burnout-composite demo with LLM-bootstrapped landscape.

    Returns dict with all results for programmatic inspection.
    """
    if envelope is None:
        envelope = ENVELOPE_HYBRID if use_hybrid else ENVELOPE_GREEDY

    source_text = composite_source_text()

    print("=" * 64)
    print("E₀ Controller — Burnout Composite Demo (Domäne 3)")
    print("=" * 64)
    print(f"\nFragmente: {len(ALL_FRAGMENTS)}")
    for label in ALL_FRAGMENTS:
        print(f"  • {label}")
    print(f"\nEnvelope: {envelope.summary()}")

    # 1. Setup LLM adapter
    if use_mock:
        print("\nMode: MOCK (no API calls)")
        adapter = E0LLMAdapter(call_fn=mock_llm_call)
    else:
        config = LLMConfig(model="gpt-4.1-mini", temperature=0.3, max_tokens=2048)
        adapter = E0LLMAdapter(config=config)
        print(f"\nMode: LIVE (model={config.model})")

    # 2. LLM designs the landscape from source text
    print("\n── Step 1: LLM generates landscape from 5 fragments ──")
    task_with_source = BURNOUT_TASK + source_text
    proposal = adapter.build_landscape(
        task_with_source, DEFAULT_START, DEFAULT_GOAL,
        goals=set(envelope.goals) if envelope.goals else None,
    )
    print(f"   States: {len(proposal.states)}")
    for s in proposal.states:
        print(f"     • {s}")
    print(f"   Edges: {len(proposal.edges)}")
    for e in proposal.edges:
        print(f"     {e['source']:35s} → {e['target']:35s}  "
              f"(Δ={e['delta']:.2f}, R₀={e['resistance']:.2f})")

    # 3. Materialize + quality check
    L = materialize_landscape(proposal)
    task_map = task_map_from_proposal(proposal)
    print(f"\n   Landscape: {len(L.states)} states, {len(L.edges)} edges")

    print("\n── Step 1b: Graph quality check ──")
    gq = graph_quality(L, DEFAULT_START, DEFAULT_GOAL)
    print(gq.summary())
    if not gq.ok():
        print("\n*** Graph failed quality checks — proceeding anyway for analysis ***")

    # 4. Build execute function (pass source text as scenario context)
    execute_fn = adapter.as_execute_fn(
        task_map,
        scenario_block=source_text,
        result_log=(result_log := []),
    )

    # 5. Run with Session + E0Envelope
    print(f"\n── Step 2: Controller runs ({envelope.mode.value}) ──")
    session = Session(
        session_id="burnout-composite",
        landscape=L,
        execute_fn=execute_fn,
        base_dir="memos/_burnout",
        canon_refs=[CanonRef("e0-canon", "v1", "canon/e0-canon-plain.txt")],
        controller_kwargs=envelope.to_controller_kwargs(),
    )
    result = session.run(
        DEFAULT_START,
        goal=DEFAULT_GOAL,
        max_cycles=25,
        auto_save=True,
    )
    trace = result.trace

    # 6. Display results
    print(f"\n{'=' * 64}")
    print("Run Complete")
    print(f"{'=' * 64}")
    print(trace.summary())

    metrics = trace.metrics()
    print(f"\nMetrics:")
    print(f"  Steps:             {int(metrics['steps'])}")
    print(f"  Deterministic:     {metrics['deterministic_rate']:.0%}")
    print(f"  Success rate:      {metrics['success_rate']:.0%}")
    print(f"  Avg tension:       {metrics['avg_tension']:.4f}")
    print(f"  Unique states:     {int(metrics['unique_states'])}")
    print(f"  Revisits:          {int(metrics['revisit_count'])}")
    if envelope.mode != HybridMode.GREEDY:
        print(f"  Hybrid overrides:  {int(metrics['hybrid_override_count'])}")
        print(f"  Override rate:     {metrics['hybrid_override_rate']:.0%}")

    # 6b. Transition details
    if result_log:
        print(f"\n── Transition Details ──")
        for i, (step, res) in enumerate(zip(trace.steps, result_log)):
            esc = " [ESCALATION]" if step.escalated else ""
            print(f"\n  Step {i+1}: {step.source} → {step.target}{esc}")
            print(f"    Outcome:    {step.outcome.name} (confidence: {res.confidence:.0%})")
            print(f"    S_eff:      {step.s_eff:.4f}")
            if res.result:
                text = res.result[:200] + ("..." if len(res.result) > 200 else "")
                print(f"    LLM Result: {text}")

    # 7. Evaluation
    print(f"\n── Step 3: Evaluation ──")
    m = metrics
    reached_goal = DEFAULT_GOAL in trace.path
    happy_path = None
    try:
        from e0_controller.graph_validation import find_happy_path
        happy_path = find_happy_path(L, DEFAULT_START, DEFAULT_GOAL)
    except Exception:
        pass
    happy_len = len(happy_path) - 1 if happy_path else len(trace.steps)

    eval_result = evaluate_run(
        path=trace.path,
        steps=int(m["steps"]),
        escalation_count=int(m.get("escalation_count", 0)),
        revisit_count=int(m["revisit_count"]),
        success_rate=m["success_rate"],
        avg_tension=m["avg_tension"],
        total_tension=trace.total_tension,
        reached_goal=reached_goal,
        happy_path_length=happy_len,
    )
    print(f"  Rating:    {eval_result.rating}")
    print(f"  Loops:     {eval_result.repeated_cycles}")
    print(f"  Imbalance: {eval_result.path_count_imbalance_max:.2f}")

    # 8. Reflection
    print(f"\n── Step 4: Reflection ──")
    scenario_eval = ScenarioEvaluation(
        scenario_id="burnout-composite",
        domain="burnout",
        graph_score=gq.score,
        run_evaluation=eval_result,
        semantic_evaluation=None,
        hard_failure=None,
        overall_score=None,
    )
    decision = should_reflect(scenario_eval)
    print(f"  Should reflect: {decision.reflect}")
    if decision.reflect:
        print(f"  Reason: {decision.reason}")
        report = reflect(scenario_eval, decision, L)
        print(format_reflection_report([report]))

    # 9. Summary
    print(f"\n{'=' * 64}")
    print("Burnout-Composite: Domäne 3 complete")
    print(f"{'=' * 64}")
    print(f"\nEnvelope:   {envelope.summary()}")
    print(f"Goal:       {'REACHED' if reached_goal else 'MISSED'}")
    print(f"Rating:     {eval_result.rating}")
    print(f"Fragments:  {len(ALL_FRAGMENTS)} → {len(proposal.states)} states, "
          f"{len(proposal.edges)} edges")
    if not use_mock:
        print(f"\n⚠  This landscape was generated by the LLM, not pre-designed.")
        print(f"   The topology reflects the LLM's understanding of the source material.")

    return {
        "envelope": envelope,
        "proposal": proposal,
        "landscape": L,
        "trace": trace,
        "evaluation": eval_result,
        "result_log": result_log,
        "graph_quality": gq,
    }


if __name__ == "__main__":
    use_mock = "--mock" in sys.argv
    use_hybrid = "--hybrid" in sys.argv
    run_demo(use_mock=use_mock, use_hybrid=use_hybrid)
