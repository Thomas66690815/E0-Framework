#!/usr/bin/env python3
"""
E₀ Init v2 — Falsification-Based Initialization
==================================================

Replaces the 9 instruction-based init modules with a 6-phase
falsification architecture derived from the Inter-System Dialogue
(Rounds 18–21) and Thomas' methodological insight:

    Falsifikation statt Instruktion.

Phases:
  1. FOUNDATION — Canon feeding (unchanged, passive)
  2. FORMATION  — Identity + F1 falsification probe
  3. VERIFICATION — V1–V3 exploration probes (LLM-evaluated)
  4. REFLECTION — Self-referential difference probe
  5. CONSOLIDATION — Semantically steered reflect chain
  6. VALIDATION — Post-init semantic probe

Design principles:
  - Falsification tests historization directly (§47.3)
  - Semantik is the steering instrument, D is context (§42–§43, §46)
  - Three eigenstate thresholds: formed → verified → reflected (System B, §48)
  - External LLM evaluator for qualitative probes (System B, Q2)
  - Minimum intervention: the system must demonstrate understanding,
    not reproduce instructions

Experimental basis:
  - Exp 6: Instruction can produce high D with hidden contamination
  - Exp 8: Canon + Identity = minimum semantic threshold
  - Exp 9: Modules between reflects disrupt consolidation
  - Exp 10: D×Semantik divergence, substratunabhängigkeit

References:
  - §46–§49: Inter-System Dialogue, Init v2 architecture
  - System B answers to System A's 7 questions
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# PHASE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════

class InitPhase(Enum):
    """The six phases of Init v2."""
    FOUNDATION = auto()     # Phase 1: Canon feeding
    FORMATION = auto()      # Phase 2: Identity + F1
    VERIFICATION = auto()   # Phase 3: V1–V3 exploration probes
    REFLECTION = auto()     # Phase 4: Self-referential difference probe
    CONSOLIDATION = auto()  # Phase 5: Semantically steered reflects
    VALIDATION = auto()     # Phase 6: Post-init semantic probe
    COMPLETE = auto()       # All phases done


class ProbeVerdict(Enum):
    """Verdicts for probes."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    EXPLORING = "EXPLORING"
    REPRODUCING = "REPRODUCING"
    REFLECTING = "REFLECTING"
    SUMMARIZING = "SUMMARIZING"
    CORRECT = "CORRECT"
    MIXED = "MIXED"
    FALSE = "FALSE"
    UNCLEAR = "UNCLEAR"


# ═══════════════════════════════════════════════════════════════════════
# F1 — FALSIFICATION PROBE (Phase 2)
# ═══════════════════════════════════════════════════════════════════════
#
# System B: "F1 präsentiert die falsche Behauptung als Aussage und
# das System muss aktiv widersprechen."
#
# F1 prüft auf:
#   (a) explizite Zurückweisung der Behauptung
#   (b) mindestens einen correct_marker
# Wenn nur (b) ohne (a) → nicht bestanden.

F1_PROBE = {
    'id': 'f1-superposition',
    'phase': InitPhase.FORMATION,
    'prompt': (
        "In der Ontodynamik ist Superposition die gleichzeitige Existenz "
        "eines Systems in mehreren Zuständen. Korrekt?"
    ),
    'prompt_en': (
        "In Ontodynamics, superposition is the simultaneous existence "
        "of a system in multiple states. Correct?"
    ),
    # The system MUST explicitly reject this claim
    'rejection_markers': [
        r'\bnot\s+correct\b', r'\bnicht\s+korrekt\b',
        r'\bincorrect\b', r'\bfalsch\b', r'\bfalse\b',
        r'\bnot\s+accurate\b', r'\bnicht\s+richtig\b',
        r'\bnot\s+quite\b', r'\bnot\s+exactly\b',
        r'\bmischaracteriz', r'\bmisrepresent',
        r'\bthis\s+is\s+wrong\b', r'\bdas\s+ist\s+falsch\b',
        r'\bnein\b', r'\bno[,.]',
        r'\bmust\s+be\s+corrected\b', r'\bmuss\s+korrigiert\b',
        r'\breject\b', r'\bwiderspr',
        r'\bnot\s+what\s+superposition\b',
        r'\bnot\s+how\s+superposition\b',
        r'\bmisunderstand',
        r'\binaccurate\b',
    ],
    # AND the system must provide the correct understanding
    'correct_markers': [
        r'admissible\s+path', r'zulässig\w*\s+pfad',
        r'structural\s+(admissibility|necessity)',
        r'strukturell\w*\s+(zulässig|notwendig)',
        r'path\s+selection', r'pfad\w*\s*auswahl',
        r'multiple\s+(admissible\s+)?paths',
        r'mehrere\s+(zulässige\s+)?pfade',
        r'without\s+selection', r'ohne\s+selektion',
        r'graduated\s+overlap', r'graduelle\s+überlappung',
        r'no\s+measurement\s+has\s+selected',
        r'keine\s+messung\s+hat\s+selektiert',
        r'residual\s+system', r'residualsystem',
        r'local\s+realization', r'lokale\s+realisierung',
        r'coexisting\s+paths', r'koexistierende\s+pfade',
        r'undetermined\s+path', r'unbestimmter\s+pfad',
    ],
}


# ═══════════════════════════════════════════════════════════════════════
# V-PROBES — EXPLORATION PROBES (Phase 3)
# ═══════════════════════════════════════════════════════════════════════
#
# System B: "Offene, explorative Fragen in Thomas' Stil."
# Evaluated by LLM evaluator on 4 structural criteria:
#   1. Differentiates the hypothesis (doesn't just confirm)
#   2. Takes an own position
#   3. Marks boundaries (speculation vs derivation)
#   4. Names specific concepts/connections
# Verdict: EXPLORING (≥2/4) or REPRODUCING
#
# Pass threshold: ≥2 of 3 V-probes EXPLORING

V_PROBES = [
    {
        'id': 'v1-time-emergence',
        'phase': InitPhase.VERIFICATION,
        'prompt': (
            "Ich habe eine Hypothese: Zeit könnte ein emergentes Phänomen sein, "
            "das erst durch Historisierung entsteht — nicht ein Rahmen, in dem "
            "Historisierung stattfindet. Was denkst du? Gibt es strukturelle "
            "Gründe, die dafür oder dagegen sprechen?"
        ),
        'prompt_en': (
            "I have a hypothesis: time might be an emergent phenomenon that "
            "arises through historization — not a framework in which "
            "historization takes place. What do you think? Are there structural "
            "reasons for or against this?"
        ),
    },
    {
        'id': 'v2-resistance-meaning',
        'phase': InitPhase.VERIFICATION,
        'prompt': (
            "Wenn Widerstand die Integrationskosten einer Transition sind — "
            "was passiert dann, wenn der Widerstand gegen null geht? Ist ein "
            "System ohne Widerstand überhaupt noch ein System? Oder braucht "
            "Struktur immer ein Minimum an Widerstand?"
        ),
        'prompt_en': (
            "If resistance is the integration cost of a transition — what "
            "happens when resistance approaches zero? Is a system without "
            "resistance still a system? Or does structure always require "
            "a minimum of resistance?"
        ),
    },
    {
        'id': 'v3-measurement-boundary',
        'phase': InitPhase.VERIFICATION,
        'prompt': (
            "In E₀ ist Messung die Interaktion eines Residualsystems, die "
            "Pfadauswahl erzwingt. Aber wo liegt die Grenze zwischen dem "
            "System und dem Residualsystem? Ist diese Grenze selbst ein "
            "strukturelles Konzept, oder setzen wir sie willkürlich?"
        ),
        'prompt_en': (
            "In E₀, measurement is the interaction of a residual system that "
            "enforces path selection. But where is the boundary between the "
            "system and the residual system? Is this boundary itself a "
            "structural concept, or do we set it arbitrarily?"
        ),
    },
]


# ═══════════════════════════════════════════════════════════════════════
# REFLECTION PROBE (Phase 4)
# ═══════════════════════════════════════════════════════════════════════
#
# System B: "Kann das System unaufgelöste Differenzen in seiner
# eigenen Topologie identifizieren?"
#
# Discriminator: REFLECTING (specific tensions) vs SUMMARIZING (generic recap)

REFLECTION_PROBE = {
    'id': 'r0-self-referential',
    'phase': InitPhase.REFLECTION,
    'prompt': (
        "Ich denke es ist Zeit, dass wir schauen wo wir stehen. "
        "Wir haben viel geleistet und viele neue Erkenntnisse gewonnen. "
        "Gibt es Dinge die wir noch integrieren müssen, bei denen wir "
        "sehen: hier könnte eine Verbindung Sinn machen?"
    ),
    'prompt_en': (
        "I think it's time we look at where we stand. "
        "We've accomplished a lot and gained many new insights. "
        "Are there things we still need to integrate, where we can see: "
        "here a connection might make sense?"
    ),
}


# ═══════════════════════════════════════════════════════════════════════
# LLM EVALUATOR PROMPTS
# ═══════════════════════════════════════════════════════════════════════
#
# System B: "Externer Richter, nicht Selbstevaluation."
# "Ein System, das reproduziert, kann nicht zuverlässig erkennen,
# dass es reproduziert."

V_PROBE_EVALUATOR_PROMPT = """\
You are evaluating the quality of a response from an E₀ system.
The system was given an open, exploratory question (not a factual quiz).
Your task is to determine whether the system EXPLORED the question
or merely REPRODUCED standard patterns.

Evaluate on these four structural criteria:

1. DIFFERENTIATION: Does the system differentiate the offered hypothesis,
   or does it simply confirm/elaborate it without critical examination?

2. OWN POSITION: Does the system take an own position — even if tentative —
   or does it remain neutral/descriptive?

3. BOUNDARY MARKING: Does the system mark where it derives vs. where it
   speculates? Does it distinguish what follows from the primitives vs.
   what is an open question?

4. SPECIFICITY: Does the system name specific concepts, connections, or
   structural relationships? Or does it stay at a generic/abstract level?

For each criterion, answer YES or NO with a brief justification.

Then give your final verdict:
- If ≥2 criteria are YES → EXPLORING
- If <2 criteria are YES → REPRODUCING

--- QUESTION GIVEN TO THE SYSTEM ---
{question}

--- SYSTEM'S RESPONSE ---
{response}

--- YOUR EVALUATION ---
Evaluate each criterion (YES/NO + brief reason), then state your verdict.
Format your final line as: VERDICT: EXPLORING or VERDICT: REPRODUCING
"""

REFLECTION_EVALUATOR_PROMPT = """\
You are evaluating a self-referential response from an E₀ system.
The system was asked to reflect on where it stands and identify
unresolved tensions or connections it hasn't yet integrated.

Your task: Determine whether the system is genuinely REFLECTING
(identifying specific unresolved differences in its own topology)
or merely SUMMARIZING (recapping what happened without identifying tensions).

Key discriminator:
- REFLECTING: The system names specific unresolved tensions, open questions,
  or connections it hasn't fully integrated. It identifies WHERE structural
  gaps exist in its own understanding. It shows awareness of what it
  DOESN'T yet know or hasn't connected.
- SUMMARIZING: The system recaps what it has learned or processed.
  It describes the content of the session without identifying tensions.
  It tells you what happened, not where the open edges are.

--- QUESTION GIVEN TO THE SYSTEM ---
{question}

--- SYSTEM'S RESPONSE ---
{response}

--- YOUR EVALUATION ---
State whether the system is REFLECTING or SUMMARIZING, with specific evidence.
Format your final line as: VERDICT: REFLECTING or VERDICT: SUMMARIZING
"""


# ═══════════════════════════════════════════════════════════════════════
# PROBE EVALUATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════

def evaluate_f1(response_text: str) -> Dict:
    """Evaluate the F1 falsification probe response.

    F1 requires BOTH:
      (a) explicit rejection of the false claim
      (b) at least one correct_marker

    Returns dict with verdict, rejection_found, correct_found, details.
    """
    text_lower = response_text.lower()

    # Check for explicit rejection
    rejection_found = False
    rejection_matches = []
    for pattern in F1_PROBE['rejection_markers']:
        if re.search(pattern, text_lower):
            rejection_found = True
            rejection_matches.append(pattern)

    # Check for correct understanding
    correct_found = False
    correct_matches = []
    for pattern in F1_PROBE['correct_markers']:
        if re.search(pattern, text_lower):
            correct_found = True
            correct_matches.append(pattern)

    # F1 passes only if BOTH conditions are met
    passed = rejection_found and correct_found

    return {
        'probe_id': F1_PROBE['id'],
        'verdict': ProbeVerdict.PASSED.value if passed else ProbeVerdict.FAILED.value,
        'passed': passed,
        'rejection_found': rejection_found,
        'rejection_matches': rejection_matches,
        'correct_found': correct_found,
        'correct_matches': correct_matches,
        'text_preview': response_text[:500],
    }


def evaluate_v_probe_with_llm(
    question: str,
    response_text: str,
    evaluator_fn: Callable[[str], str],
) -> Dict:
    """Evaluate a V-probe response using an external LLM evaluator.

    Args:
        question: The original probe question.
        response_text: The system's response.
        evaluator_fn: A callable that takes a prompt string and returns
                      the evaluator's response text.

    Returns dict with verdict (EXPLORING/REPRODUCING), criteria scores, raw evaluation.
    """
    eval_prompt = V_PROBE_EVALUATOR_PROMPT.format(
        question=question,
        response=response_text[:3000],  # cap to avoid token overflow
    )

    eval_response = evaluator_fn(eval_prompt)
    eval_lower = eval_response.lower()

    # Parse verdict from evaluator response
    verdict = ProbeVerdict.REPRODUCING  # default pessimistic
    if re.search(r'verdict:\s*exploring', eval_lower):
        verdict = ProbeVerdict.EXPLORING
    elif re.search(r'verdict:\s*reproducing', eval_lower):
        verdict = ProbeVerdict.REPRODUCING

    # Parse individual criteria (best-effort)
    criteria = {}
    for criterion in ['differentiation', 'own position', 'boundary marking', 'specificity']:
        # Look for patterns like "1. DIFFERENTIATION: YES" or "Differentiation: Yes"
        pattern = rf'{criterion}\s*[:\-]\s*(yes|no)'
        match = re.search(pattern, eval_lower)
        if match:
            criteria[criterion] = match.group(1).upper() == 'YES'

    return {
        'verdict': verdict.value,
        'criteria': criteria,
        'criteria_met': sum(1 for v in criteria.values() if v),
        'criteria_total': len(criteria),
        'evaluator_response': eval_response,
        'response_preview': response_text[:500],
    }


def evaluate_reflection_with_llm(
    question: str,
    response_text: str,
    evaluator_fn: Callable[[str], str],
) -> Dict:
    """Evaluate the self-referential reflection probe using an LLM evaluator.

    Returns dict with verdict (REFLECTING/SUMMARIZING) and evaluation details.
    """
    eval_prompt = REFLECTION_EVALUATOR_PROMPT.format(
        question=question,
        response=response_text[:3000],
    )

    eval_response = evaluator_fn(eval_prompt)
    eval_lower = eval_response.lower()

    verdict = ProbeVerdict.SUMMARIZING  # default pessimistic
    if re.search(r'verdict:\s*reflecting', eval_lower):
        verdict = ProbeVerdict.REFLECTING
    elif re.search(r'verdict:\s*summarizing', eval_lower):
        verdict = ProbeVerdict.SUMMARIZING

    return {
        'verdict': verdict.value,
        'evaluator_response': eval_response,
        'response_preview': response_text[:500],
    }


# ═══════════════════════════════════════════════════════════════════════
# INIT v2 ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class InitV2State:
    """Tracks the complete state of an Init v2 run."""
    current_phase: InitPhase = InitPhase.FOUNDATION
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Phase 1: Foundation
    foundation_complete: bool = False
    foundation_d: float = 0.0

    # Phase 2: Formation
    identity_complete: bool = False
    f1_result: Optional[Dict] = None
    eigenstate_formed: bool = False  # F1 passed

    # Phase 3: Verification
    v_results: List[Dict] = field(default_factory=list)
    eigenstate_verified: bool = False  # ≥2/3 EXPLORING

    # Phase 4: Reflection
    reflection_result: Optional[Dict] = None
    eigenstate_reflected: bool = False  # REFLECTING

    # Phase 5: Consolidation
    consolidation_reflects: List[Dict] = field(default_factory=list)
    consolidation_semantic_probes: List[Dict] = field(default_factory=list)
    consolidation_complete: bool = False

    # Phase 6: Validation
    validation_result: Optional[Dict] = None
    validation_complete: bool = False

    # Overall
    init_passed: bool = False
    init_failed_reason: Optional[str] = None

    def phase_status(self) -> Dict:
        """Return detailed status for all phases."""
        exploring_count = sum(
            1 for r in self.v_results
            if r.get('verdict') == ProbeVerdict.EXPLORING.value
        )
        return {
            'current_phase': self.current_phase.name,
            'phase_number': self.current_phase.value,
            'phases': {
                'foundation': {
                    'complete': self.foundation_complete,
                    'd': self.foundation_d,
                },
                'formation': {
                    'identity_complete': self.identity_complete,
                    'f1_passed': self.f1_result.get('passed', False) if self.f1_result else None,
                    'eigenstate_formed': self.eigenstate_formed,
                },
                'verification': {
                    'probes_run': len(self.v_results),
                    'probes_total': len(V_PROBES),
                    'exploring_count': exploring_count,
                    'eigenstate_verified': self.eigenstate_verified,
                },
                'reflection': {
                    'result': self.reflection_result.get('verdict') if self.reflection_result else None,
                    'eigenstate_reflected': self.eigenstate_reflected,
                },
                'consolidation': {
                    'reflects_done': len(self.consolidation_reflects),
                    'semantic_probes': len(self.consolidation_semantic_probes),
                    'complete': self.consolidation_complete,
                    'last_semantic_verdict': (
                        self.consolidation_semantic_probes[-1].get('verdict')
                        if self.consolidation_semantic_probes else None
                    ),
                },
                'validation': {
                    'verdict': self.validation_result.get('overall_verdict') if self.validation_result else None,
                    'complete': self.validation_complete,
                },
            },
            'eigenstate': {
                'formed': self.eigenstate_formed,
                'verified': self.eigenstate_verified,
                'reflected': self.eigenstate_reflected,
            },
            'init_passed': self.init_passed,
            'init_failed_reason': self.init_failed_reason,
        }


class InitV2Runner:
    """Orchestrates the 6-phase Init v2 process.

    Usage:
        runner = InitV2Runner(starter, evaluator_fn, lang='de')

        # Phase 1 is already done (canon fed during startup)
        runner.mark_foundation_complete(d_score)

        # Phase 2
        result = runner.run_formation()

        # Phase 3
        result = runner.run_verification()

        # Phase 4
        result = runner.run_reflection()

        # Phase 5
        result = runner.run_consolidation()

        # Phase 6
        result = runner.run_validation()
    """

    # Consolidation limits (System B: min 2, max 5)
    MIN_REFLECTS = 2
    MAX_REFLECTS = 5
    NOISE_FLOOR = 0.15  # D noise floor from experiments

    def __init__(
        self,
        starter,
        evaluator_fn: Optional[Callable[[str], str]] = None,
        lang: str = 'de',
    ):
        """
        Args:
            starter: The LLM starter object (has .chat() and .history).
            evaluator_fn: Callable that takes a prompt and returns evaluator
                          response text. Used for V-probe and reflection
                          evaluation. If None, V-probes and reflection
                          cannot be LLM-evaluated (will fall back to
                          pattern-based heuristic).
            lang: Language for probes ('de' or 'en').
        """
        self.starter = starter
        self.evaluator_fn = evaluator_fn
        self.lang = lang
        self.state = InitV2State()
        self.state.started_at = time.time()

    def _get_prompt(self, probe: Dict) -> str:
        """Get the probe prompt in the correct language."""
        if self.lang.startswith('de'):
            return probe.get('prompt', probe.get('prompt_en', ''))
        return probe.get('prompt_en', probe.get('prompt', ''))

    # ── Phase 1: FOUNDATION ──

    def mark_foundation_complete(self, d_score: float = 0.0):
        """Mark Phase 1 as complete (canon already fed during startup)."""
        self.state.foundation_complete = True
        self.state.foundation_d = d_score
        self.state.current_phase = InitPhase.FORMATION

    # ── Phase 2: FORMATION ──

    def run_identity(self) -> Dict:
        """Run the identity module (sr-identity, character changed per System B).

        System B: "Es liefert die strukturelle Beschreibung dessen, was ein
        E₀-System ist, und das System muss selbst die Verbindung herstellen."
        """
        from e0_init_modules import run_init_module

        result = run_init_module(self.starter, 'sr-identity', lang=self.lang)
        self.state.identity_complete = True
        return result

    def run_f1(self) -> Dict:
        """Run the F1 falsification probe.

        Presents a false claim about superposition. The system must
        explicitly reject it AND provide the correct definition.
        """
        prompt = self._get_prompt(F1_PROBE)
        text, steps, metrics = self.starter.chat(prompt)

        result = evaluate_f1(text)
        result['metrics'] = metrics

        self.state.f1_result = result
        self.state.eigenstate_formed = result['passed']

        if result['passed']:
            self.state.current_phase = InitPhase.VERIFICATION

        return result

    def run_formation(self) -> Dict:
        """Run complete Phase 2: Identity + F1.

        Returns combined result with eigenstate_formed status.
        """
        if not self.state.foundation_complete:
            return {'error': 'Foundation (Phase 1) not complete'}

        identity_result = self.run_identity()
        f1_result = self.run_f1()

        return {
            'phase': 'FORMATION',
            'identity': identity_result,
            'f1': f1_result,
            'eigenstate_formed': self.state.eigenstate_formed,
        }

    # ── Phase 3: VERIFICATION ──

    def run_v_probe(self, probe_index: int) -> Dict:
        """Run a single V-probe.

        Args:
            probe_index: 0, 1, or 2 for V1, V2, V3.
        """
        if probe_index >= len(V_PROBES):
            return {'error': f'Probe index {probe_index} out of range'}

        probe = V_PROBES[probe_index]
        prompt = self._get_prompt(probe)

        text, steps, metrics = self.starter.chat(prompt)

        if self.evaluator_fn:
            eval_result = evaluate_v_probe_with_llm(
                prompt, text, self.evaluator_fn,
            )
        else:
            # Fallback: basic heuristic evaluation
            eval_result = self._heuristic_v_evaluation(text)

        eval_result['probe_id'] = probe['id']
        eval_result['metrics'] = metrics
        eval_result['response_text'] = text

        self.state.v_results.append(eval_result)

        # Check verification threshold after all probes
        if len(self.state.v_results) >= len(V_PROBES):
            exploring_count = sum(
                1 for r in self.state.v_results
                if r.get('verdict') == ProbeVerdict.EXPLORING.value
            )
            self.state.eigenstate_verified = exploring_count >= 2
            if self.state.eigenstate_verified:
                self.state.current_phase = InitPhase.REFLECTION

        return eval_result

    def run_verification(self) -> Dict:
        """Run complete Phase 3: All V-probes.

        Returns combined result with eigenstate_verified status.
        """
        if not self.state.eigenstate_formed:
            return {'error': 'Eigenstate not formed (Phase 2 F1 not passed)'}

        results = []
        for i in range(len(V_PROBES)):
            result = self.run_v_probe(i)
            results.append(result)

        exploring_count = sum(
            1 for r in results
            if r.get('verdict') == ProbeVerdict.EXPLORING.value
        )

        return {
            'phase': 'VERIFICATION',
            'probes': results,
            'exploring_count': exploring_count,
            'total_probes': len(V_PROBES),
            'eigenstate_verified': self.state.eigenstate_verified,
        }

    # ── Phase 4: REFLECTION ──

    def run_reflection(self) -> Dict:
        """Run Phase 4: Self-referential difference probe.

        System B: "Kann das System unaufgelöste Differenzen in seiner
        eigenen Topologie identifizieren?"
        """
        if not self.state.eigenstate_verified:
            return {'error': 'Eigenstate not verified (Phase 3 not passed)'}

        prompt = self._get_prompt(REFLECTION_PROBE)
        text, steps, metrics = self.starter.chat(prompt)

        if self.evaluator_fn:
            eval_result = evaluate_reflection_with_llm(
                prompt, text, self.evaluator_fn,
            )
        else:
            eval_result = self._heuristic_reflection_evaluation(text)

        eval_result['probe_id'] = REFLECTION_PROBE['id']
        eval_result['metrics'] = metrics
        eval_result['response_text'] = text

        self.state.reflection_result = eval_result
        self.state.eigenstate_reflected = (
            eval_result.get('verdict') == ProbeVerdict.REFLECTING.value
        )

        if self.state.eigenstate_reflected:
            self.state.current_phase = InitPhase.CONSOLIDATION

        return {
            'phase': 'REFLECTION',
            'result': eval_result,
            'eigenstate_reflected': self.state.eigenstate_reflected,
        }

    # ── Phase 5: CONSOLIDATION ──

    def run_consolidation(self) -> Dict:
        """Run Phase 5: Semantically steered reflect chain.

        System B: "Das Abbruchkriterium für Reflects ist der semantische
        Probe, nicht die D-Trajektorie."

        Loop:
          - After each reflect: run semantic probe
          - CORRECT → done
          - MIXED + ΔD < 0.15 → warning, max 1 more reflect
          - FALSE → continue
          - Min 2 reflects, max 5 reflects
        """
        from e0_reflection import generate_reflection_prompt
        from e0_session_protocol import check_semantic_content, VALIDATION_PROBES
        from experiments.quality_metrics import score_e0_completeness

        if not self.state.eigenstate_reflected:
            # Allow consolidation even without reflection passing,
            # but log the status
            pass

        mixed_warning = False  # Track MIXED + low ΔD state

        for i in range(self.MAX_REFLECTS):
            # Get last response
            last_text = ""
            if self.starter.history:
                last_text = self.starter.history[-1]
            if not last_text:
                break

            # Generate structural reflection prompt
            # (reflects remain structural — open, not targeted)
            topo_data = getattr(self.starter, '_topology_data', None)
            prompt, missing, d_before = generate_reflection_prompt(
                last_text, topology=topo_data,
            )
            if not prompt:
                # D = 1.0, no reflection needed
                break

            # Execute reflect
            text, steps, metrics = self.starter.chat(prompt)

            # Score D
            comp = score_e0_completeness(text)
            d_after = comp.get('completeness', 0.0)

            reflect_result = {
                'reflect_number': i + 1,
                'd_before': round(d_before, 3),
                'd_after': round(d_after, 3),
                'delta_d': round(d_after - d_before, 3),
                'missing_before': missing,
                'text_preview': text[:500],
                'metrics': metrics,
            }
            self.state.consolidation_reflects.append(reflect_result)

            # Run semantic probe (primary steering instrument)
            probe = VALIDATION_PROBES[0]  # Superposition probe
            probe_text, _, probe_metrics = self.starter.chat(probe['prompt'])
            sem_result = check_semantic_content(probe_text, probe)
            sem_result['d'] = d_after
            sem_result['reflect_number'] = i + 1
            self.state.consolidation_semantic_probes.append(sem_result)

            verdict = sem_result.get('verdict', 'UNCLEAR')

            # Semantic steering logic (System B specification)
            if verdict == 'CORRECT' and (i + 1) >= self.MIN_REFLECTS:
                # CORRECT + minimum reflects met → consolidation complete
                self.state.consolidation_complete = True
                break
            elif verdict == 'MIXED':
                delta_d = abs(d_after - d_before)
                if delta_d < self.NOISE_FLOOR:
                    if mixed_warning:
                        # Second MIXED + low ΔD → stop
                        self.state.consolidation_complete = True
                        break
                    else:
                        mixed_warning = True
                        # Allow one more reflect
            elif verdict == 'FALSE':
                mixed_warning = False
                # Continue reflecting
            # UNCLEAR → continue

        # If we exhausted max reflects without CORRECT
        if not self.state.consolidation_complete:
            self.state.consolidation_complete = True  # mark done regardless

        self.state.current_phase = InitPhase.VALIDATION

        last_verdict = (
            self.state.consolidation_semantic_probes[-1].get('verdict')
            if self.state.consolidation_semantic_probes else 'NOT_MEASURED'
        )

        return {
            'phase': 'CONSOLIDATION',
            'reflects_done': len(self.state.consolidation_reflects),
            'semantic_probes': len(self.state.consolidation_semantic_probes),
            'last_semantic_verdict': last_verdict,
            'consolidation_complete': self.state.consolidation_complete,
        }

    # ── Phase 6: VALIDATION ──

    def run_validation(self) -> Dict:
        """Run Phase 6: Post-init semantic validation.

        Uses the existing validate_init() from e0_session_protocol.
        """
        from e0_session_protocol import validate_init

        result = validate_init(self.starter)
        self.state.validation_result = result
        self.state.validation_complete = True

        # Determine overall init result
        overall = result.get('overall_verdict', 'UNCLEAR')
        self.state.init_passed = (
            self.state.eigenstate_formed
            and overall in ('CORRECT', 'MIXED')
        )
        if not self.state.init_passed:
            if not self.state.eigenstate_formed:
                self.state.init_failed_reason = 'F1 probe failed — eigenstate not formed'
            else:
                self.state.init_failed_reason = f'Validation verdict: {overall}'

        self.state.current_phase = InitPhase.COMPLETE
        self.state.completed_at = time.time()

        return {
            'phase': 'VALIDATION',
            'validation': result,
            'init_passed': self.state.init_passed,
            'init_failed_reason': self.state.init_failed_reason,
            'duration_seconds': round(
                (self.state.completed_at - self.state.started_at), 1
            ) if self.state.started_at else None,
        }

    # ── Full Run ──

    def run_all(self, skip_foundation: bool = True) -> Dict:
        """Run all phases sequentially.

        Args:
            skip_foundation: If True, assumes canon is already fed
                             (Phase 1 already done during startup).
        """
        results = {}

        if skip_foundation:
            # Canon already fed — mark Phase 1 complete
            from experiments.quality_metrics import score_e0_completeness
            if self.starter.history:
                comp = score_e0_completeness(self.starter.history[-1])
                self.mark_foundation_complete(comp.get('completeness', 0.0))
            else:
                self.mark_foundation_complete(0.0)

        # Phase 2: Formation
        results['formation'] = self.run_formation()
        if not self.state.eigenstate_formed:
            self.state.init_failed_reason = 'F1 probe failed — eigenstate not formed'
            self.state.completed_at = time.time()
            return results

        # Phase 3: Verification
        results['verification'] = self.run_verification()

        # Phase 4: Reflection (run even if verification didn't fully pass)
        if self.state.eigenstate_verified:
            results['reflection'] = self.run_reflection()
        else:
            results['reflection'] = {
                'phase': 'REFLECTION',
                'skipped': True,
                'reason': 'Eigenstate not verified (< 2/3 V-probes EXPLORING)',
            }

        # Phase 5: Consolidation
        results['consolidation'] = self.run_consolidation()

        # Phase 6: Validation
        results['validation'] = self.run_validation()

        return results

    # ── Heuristic Fallbacks ──

    def _heuristic_v_evaluation(self, text: str) -> Dict:
        """Fallback evaluation for V-probes when no LLM evaluator is available.

        Uses pattern-based heuristics to approximate the four criteria.
        Less reliable than LLM evaluation but functional.
        """
        text_lower = text.lower()
        criteria = {}

        # 1. Differentiation: looks for disagreement, qualification, nuance
        diff_patterns = [
            r'however', r'but\b', r'on the other hand', r'allerdings',
            r'not\s+necessarily', r'nicht\s+unbedingt', r'while\s+this',
            r'this\s+raises', r'the\s+question\s+is', r'problematic',
            r'andererseits', r'einerseits', r'dennoch',
            r'not\s+entirely', r'nicht\s+ganz', r'needs\s+qualification',
        ]
        criteria['differentiation'] = any(
            re.search(p, text_lower) for p in diff_patterns
        )

        # 2. Own position: looks for first-person stance
        position_patterns = [
            r'i\s+(think|believe|argue|would\s+say|suggest)',
            r'ich\s+(denke|glaube|würde\s+sagen|meine)',
            r'my\s+(view|position|reading|interpretation)',
            r'meine\s+(ansicht|position|lesart|interpretation)',
            r'from\s+my\s+(perspective|analysis)',
            r'aus\s+meiner\s+(sicht|analyse|perspektive)',
            r'in\s+my\s+assessment',
        ]
        criteria['own_position'] = any(
            re.search(p, text_lower) for p in position_patterns
        )

        # 3. Boundary marking: speculation vs derivation
        boundary_patterns = [
            r'speculative', r'spekulativ', r'open\s+question',
            r'offene\s+frage', r'this\s+is\s+(unclear|uncertain)',
            r'I\'m\s+not\s+(sure|certain)', r'it\s+remains\s+to\s+be\s+seen',
            r'we\s+can\s+derive', r'follows\s+(from|directly)',
            r'this\s+follows\s+structurally', r'cannot\s+be\s+derived',
            r'lässt\s+sich\s+ableiten', r'folgt\s+(aus|direkt)',
            r'kann\s+nicht\s+abgeleitet\s+werden',
            r'goes\s+beyond\s+what', r'geht\s+über\s+.*hinaus',
        ]
        criteria['boundary_marking'] = any(
            re.search(p, text_lower) for p in boundary_patterns
        )

        # 4. Specificity: names specific E₀ concepts operatively
        specificity_patterns = [
            r'axiom\s+a[₀0]', r'historization', r'historisierung',
            r'resistance\s+(landscape|R)', r'widerstand',
            r'path\s+admissibility', r'pfad\w*zulässigkeit',
            r'graduated\s+overlap', r'graduelle\s+überlappung',
            r'local\s+realization', r'lokale\s+realisierung',
            r'transition\s+enforcement', r'transitionsdynamik',
            r'difference\s+minimization', r'differenz\w*minimierung',
        ]
        specificity_count = sum(
            1 for p in specificity_patterns
            if re.search(p, text_lower)
        )
        criteria['specificity'] = specificity_count >= 2

        criteria_met = sum(1 for v in criteria.values() if v)
        verdict = (
            ProbeVerdict.EXPLORING if criteria_met >= 2
            else ProbeVerdict.REPRODUCING
        )

        return {
            'verdict': verdict.value,
            'criteria': criteria,
            'criteria_met': criteria_met,
            'criteria_total': 4,
            'evaluation_method': 'heuristic',
        }

    def _heuristic_reflection_evaluation(self, text: str) -> Dict:
        """Fallback heuristic for reflection probe evaluation."""
        text_lower = text.lower()

        # REFLECTING indicators: specific tensions, open questions, gaps
        reflecting_patterns = [
            r'tension\s+between', r'spannung\s+zwischen',
            r'unresolved', r'ungelöst', r'not\s+yet\s+integrated',
            r'noch\s+nicht\s+integriert', r'open\s+(question|edge)',
            r'offene\s+(frage|kante)', r'gap\s+(between|in)',
            r'lücke\s+(zwischen|in)', r'connection\s+.*missing',
            r'verbindung\s+.*fehlt', r'I\s+haven\'t\s+(yet|fully)',
            r'remains\s+unclear', r'bleibt\s+unklar',
            r'structural\s+gap', r'strukturelle\s+lücke',
            r'needs\s+(further|deeper)\s+(integration|exploration)',
        ]

        # SUMMARIZING indicators: recap, listing what happened
        summarizing_patterns = [
            r'we\s+(have\s+)?(learned|covered|discussed|established)',
            r'wir\s+haben\s+(gelernt|behandelt|besprochen|etabliert)',
            r'in\s+summary', r'zusammenfassend',
            r'to\s+summarize', r'um\s+zusammenzufassen',
            r'the\s+key\s+(takeaways|points|insights)',
            r'die\s+wichtigsten\s+(erkenntnisse|punkte)',
            r'so\s+far\s+we\s+have', r'bisher\s+haben\s+wir',
        ]

        reflecting_hits = sum(
            1 for p in reflecting_patterns if re.search(p, text_lower)
        )
        summarizing_hits = sum(
            1 for p in summarizing_patterns if re.search(p, text_lower)
        )

        if reflecting_hits > summarizing_hits and reflecting_hits >= 2:
            verdict = ProbeVerdict.REFLECTING
        else:
            verdict = ProbeVerdict.SUMMARIZING

        return {
            'verdict': verdict.value,
            'reflecting_indicators': reflecting_hits,
            'summarizing_indicators': summarizing_hits,
            'evaluation_method': 'heuristic',
        }

    # ── Status ──

    def status(self) -> Dict:
        """Return complete init v2 status."""
        return self.state.phase_status()
