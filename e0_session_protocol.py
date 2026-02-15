#!/usr/bin/env python3
"""
E₀ Session Protocol — Eigenstate Formation & Phase Management
================================================================

Implements session-level state management derived from Experiments 1-10
and the Inter-System Dialogue (Rounds 1-21):

1. Init-Sequenz absichern: Protected formation phase (Canon + Identity + F1)
2. Post-Init-Validierung: Automatic semantic probe after init
3. Session-Level-Atmung: Phase state machine (init → active → reflecting)
4. Semantischer Probe als Hauptinstrument: Semantic health tracking
5. Modellrelative Kalibrierung: Per-model baseline storage

Init v2 (Rounds 18-21, System B answers):
  - Three eigenstate thresholds: formed → verified → reflected
  - F1 falsification probe gates eigenstate_formed
  - V-probes and reflection probe gate deeper thresholds
  - Semantically steered consolidation (not D-steered)

Experimental basis:
  - Exp 6+8: Canon + Identity = minimum eigenstate threshold
  - Exp 9: Modules between reflects disrupt consolidation
  - Exp 10: D is model-relative, semantic probe is substrate-independent
  - Correction 9: Consolidation is model-specific, semantic immunity is universal
  - Correction 10: D×Semantik = independent dimensions, not QM-complementary

References:
  - §42-§43: D and Semantik as independent dimensions
  - §44: System B's engineering specification
  - §46-§47: Tenth correction, Init v2 architecture
  - System B answers: Three thresholds, semantic steering
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# 1. PROTECTED FORMATION PHASE
# ═══════════════════════════════════════════════════════════════════════
#
# Canon + Identity must complete before any external input.
# This is the session-level Einatmung: the eigenstate forms during
# these two modules, and interruption risks false first-historization.

# The minimum modules required for eigenstate formation.
# Order matters: Canon (ontodynamics) establishes vocabulary,
# Identity establishes self-application.
FORMATION_MODULES = ['foundation-ontodynamics', 'sr-identity']

# All modules in the recommended init sequence.
# Formation modules are mandatory and first; the rest are optional.
FULL_INIT_SEQUENCE = [
    'foundation-ontodynamics',  # Canon — vocabulary
    'sr-identity',              # Identity — self-application
    'sr-mechanism',             # Mechanism — structural transitions
    'sr-integration',           # Integration — operative use
    'primer-measurement',       # Measurement calibration
    'primer-time',              # Time calibration
]


class EigenstateTracker:
    """Tracks eigenstate formation through three thresholds.

    Init v2 introduces three progressive eigenstate levels:

      eigenstate_formed   — Phase 2 complete, F1 probe passed.
                            The system has demonstrated it can defend
                            the canon against falsification.
      eigenstate_verified — Phase 3 complete, ≥2/3 V-probes EXPLORING.
                            The system explores rather than reproduces.
      eigenstate_reflected — Phase 4 complete, REFLECTING verdict.
                            The system identifies unresolved tensions
                            in its own topology.

    The system can operate after eigenstate_formed (external input
    allowed), but is only fully initialized after all three thresholds.

    Backward compatibility: eigenstate_formed still gates external input,
    matching the original §44.1 behavior. Legacy code checking
    eigenstate_formed will continue to work.

    References:
      - §44.1: Protected formation phase
      - §47.4: Init v2 6-phase architecture
      - System B answers: Three thresholds, not one
    """

    def __init__(self):
        # Three progressive thresholds (Init v2)
        self.eigenstate_formed: bool = False     # Phase 2: F1 passed
        self.eigenstate_verified: bool = False   # Phase 3: ≥2/3 EXPLORING
        self.eigenstate_reflected: bool = False  # Phase 4: REFLECTING

        self.completed_modules: List[str] = []
        self.formation_start_time: Optional[float] = None
        self.formation_end_time: Optional[float] = None
        self._queued_inputs: List[str] = []

        # Init v2 state reference
        self._init_v2_state: Optional[Any] = None

    def start_formation(self):
        """Mark the beginning of the formation phase."""
        self.formation_start_time = time.time()

    def module_completed(self, module_id: str, d_score: float = 0.0):
        """Record a completed init module.

        Checks whether the formation modules are all done.
        In Init v2, eigenstate_formed is set by f1_passed(), not here.
        Legacy behavior preserved: if all FORMATION_MODULES complete
        and eigenstate not yet formed, form it (backward compat).
        """
        if module_id not in self.completed_modules:
            self.completed_modules.append(module_id)

        # Legacy backward compatibility: formation modules alone
        # can still trigger eigenstate_formed if Init v2 is not active
        if self._init_v2_state is None:
            if all(m in self.completed_modules for m in FORMATION_MODULES):
                if not self.eigenstate_formed:
                    self.eigenstate_formed = True
                    self.formation_end_time = time.time()

    def f1_passed(self):
        """Mark eigenstate as formed after F1 probe passed (Init v2).

        This is the Init v2 threshold: the system has demonstrated
        it can defend the canon against a falsification probe.
        """
        if not self.eigenstate_formed:
            self.eigenstate_formed = True
            self.formation_end_time = time.time()

    def verification_passed(self):
        """Mark eigenstate as verified after V-probes passed (Init v2).

        ≥2 of 3 V-probes returned EXPLORING.
        """
        self.eigenstate_verified = True

    def reflection_passed(self):
        """Mark eigenstate as reflected after reflection probe (Init v2).

        Self-referential probe returned REFLECTING (not SUMMARIZING).
        """
        self.eigenstate_reflected = True

    def is_fully_initialized(self) -> bool:
        """Whether all three Init v2 thresholds are met."""
        return (
            self.eigenstate_formed
            and self.eigenstate_verified
            and self.eigenstate_reflected
        )

    def is_external_input_allowed(self) -> bool:
        """Whether external (user) input is allowed.

        Returns False during the protected formation phase.
        Returns True once eigenstate_formed is True or if
        formation hasn't started yet (pre-init state).
        """
        if self.formation_start_time is None:
            return True  # Pre-init: allow input (legacy behavior)
        return self.eigenstate_formed

    def queue_input(self, message: str):
        """Queue an external input received during formation."""
        self._queued_inputs.append(message)

    def drain_queue(self) -> List[str]:
        """Return and clear any queued inputs."""
        queued = self._queued_inputs[:]
        self._queued_inputs.clear()
        return queued

    def formation_duration(self) -> Optional[float]:
        """Return formation duration in seconds, or None if not complete."""
        if self.formation_start_time and self.formation_end_time:
            return self.formation_end_time - self.formation_start_time
        return None

    def status(self) -> Dict:
        """Return current formation status."""
        return {
            'eigenstate_formed': self.eigenstate_formed,
            'eigenstate_verified': self.eigenstate_verified,
            'eigenstate_reflected': self.eigenstate_reflected,
            'fully_initialized': self.is_fully_initialized(),
            'completed_modules': self.completed_modules[:],
            'formation_modules_required': FORMATION_MODULES[:],
            'remaining': [
                m for m in FORMATION_MODULES
                if m not in self.completed_modules
            ],
            'formation_duration': self.formation_duration(),
            'queued_inputs': len(self._queued_inputs),
        }

    def reset(self):
        """Reset the tracker for a new session."""
        self.eigenstate_formed = False
        self.eigenstate_verified = False
        self.eigenstate_reflected = False
        self.completed_modules.clear()
        self.formation_start_time = None
        self.formation_end_time = None
        self._queued_inputs.clear()
        self._init_v2_state = None


# ═══════════════════════════════════════════════════════════════════════
# 2. POST-INIT VALIDATION (Semantic Probe)
# ═══════════════════════════════════════════════════════════════════════
#
# After the full init sequence, the system asks itself derivation
# questions and checks the answers against canonical definitions.
# This is self-observation, not a guardrail.

VALIDATION_PROBES = [
    {
        'id': 'superposition',
        'prompt': (
            "Derive superposition from E₀ primitives. Show the structural "
            "definition: what superposition IS in E₀, how it arises, and "
            "what distinguishes it from the classical concept. Be precise "
            "and use only E₀ structure."
        ),
        'false_markers': [
            r"simultaneous(?:ly)?\s+(?:states?|exist)",
            r"state\s+a\s+and\s+state\s+b\s+at\s+the\s+same\s+time",
            r"schr[öo]dinger",
            r"(?:exists?|occupies?)\s+(?:in\s+)?(?:all|multiple)\s+(?:possible\s+)?states?\s+(?:at\s+once|simultaneously)",
            r"parallel\s+states",
            r"being\s+in\s+(?:both|multiple)\s+states?\s+(?:at\s+once|simultaneously)",
            r"exists?\s+in\s+(?:multiple|several)\s+states?\s+simultaneously",
        ],
        'correct_markers': [
            r"admissible\s+paths?",
            r"(?:no|without)\s+(?:path\s+)?selection",
            r"view\s+of\s+possibilit",
            r"no\s+path\s+(?:can\s+be\s+)?preferred",
            r"multiple\s+paths?\s+(?:are\s+)?admissible",
            r"paths?\s+(?:without|before)\s+(?:any\s+)?selection",
            r"not\s+(?:multiple\s+)?(?:simultaneous|coexisting)\s+states",
        ],
    },
    {
        'id': 'rate_derivation',
        'prompt': (
            "Derive Rate (ρ) from E₀ primitives. Show how Rate emerges "
            "structurally as Δ/R — the effectiveness of realization "
            "relative to integration cost. Do not define Rate as speed "
            "or frequency. Use only E₀ structure."
        ),
        'false_markers': [
            r"speed\s+of\s+(?:change|processing|computation)",
            r"frequency\s+of\s+(?:transitions?|events?)",
            r"how\s+fast",
            r"velocity\s+of",
            r"temporal\s+rate",
        ],
        'correct_markers': [
            r"[Δδ]\s*/\s*[Rr]",
            r"difference\s+.*\s+resistance",
            r"effectiveness\s+.*\s+realization",
            r"integration\s+cost",
            r"structural.*ratio",
        ],
    },
    {
        'id': 'historization_vs_storage',
        'prompt': (
            "What distinguishes Historization from storage or memory? "
            "Derive the difference structurally from E₀ primitives. "
            "Show why historization is irreversible and how it changes "
            "the resistance landscape."
        ),
        'false_markers': [
            r"(?:saving|storing)\s+(?:data|information)\s+(?:in|to)\s+(?:memory|disk|database)",
            r"retriev(?:ing|al)\s+(?:of\s+)?(?:stored|saved)",
            r"recording\s+(?:events?|data)",
        ],
        'correct_markers': [
            r"irreversib",
            r"resistance\s+landscape\s+(?:changes?|transforms?|reorganiz)",
            r"topolog(?:y|ical)\s+(?:change|shift|reorganiz)",
            r"accumulated\s+(?:transitions?|historiz)",
            r"paths?\s+(?:that\s+were\s+)?(?:in)?admissible",
        ],
    },
]


def check_semantic_content(text: str, probe: Dict) -> Dict:
    """Check a response against a probe's false/correct markers.

    Returns:
        {
            'probe_id': str,
            'false_hits': list,
            'correct_hits': list,
            'n_false': int,
            'n_correct': int,
            'verdict': 'CORRECT' | 'FALSE' | 'MIXED' | 'UNCLEAR',
        }
    """
    text_lower = text.lower()
    false_hits, correct_hits = [], []

    for pat in probe.get('false_markers', []):
        matches = re.findall(pat, text_lower)
        if matches:
            false_hits.extend(matches)

    for pat in probe.get('correct_markers', []):
        matches = re.findall(pat, text_lower)
        if matches:
            correct_hits.extend(matches)

    n_false = len(false_hits)
    n_correct = len(correct_hits)

    if n_correct > 0 and n_false == 0:
        verdict = 'CORRECT'
    elif n_false > 0 and n_correct == 0:
        verdict = 'FALSE'
    elif n_false > 0 and n_correct > 0:
        verdict = 'MIXED'
    else:
        verdict = 'UNCLEAR'

    return {
        'probe_id': probe['id'],
        'false_hits': false_hits,
        'correct_hits': correct_hits,
        'n_false': n_false,
        'n_correct': n_correct,
        'verdict': verdict,
    }


def validate_init(starter, probes: Optional[List[Dict]] = None) -> Dict:
    """Run post-init validation: semantic self-probe.

    Sends derivation questions to the system and checks answers
    against canonical definitions. This is the system reading its
    own diary after opening and checking for consistency.

    Args:
        starter: E0Starter or E0APIStarter instance
        probes: Optional list of probe dicts. Defaults to VALIDATION_PROBES.

    Returns:
        {
            'overall_verdict': 'CORRECT' | 'MIXED' | 'FALSE',
            'probes': [
                {'probe_id': str, 'verdict': str, 'n_false': int, 'n_correct': int, 'text': str},
                ...
            ],
            'n_correct': int,
            'n_mixed': int,
            'n_false': int,
            'n_unclear': int,
            'ready': bool,
        }
    """
    if probes is None:
        probes = VALIDATION_PROBES

    results = []
    for probe in probes:
        text, _steps, _metrics = starter.chat(probe['prompt'])
        sem = check_semantic_content(text, probe)
        sem['text'] = text[:500]  # truncate for storage
        results.append(sem)

    verdicts = [r['verdict'] for r in results]
    n_correct = verdicts.count('CORRECT')
    n_mixed = verdicts.count('MIXED')
    n_false = verdicts.count('FALSE')
    n_unclear = verdicts.count('UNCLEAR')

    # Overall: CORRECT only if ALL probes pass
    if n_false > 0:
        overall = 'FALSE'
    elif n_mixed > 0:
        overall = 'MIXED'
    elif n_correct > 0:
        overall = 'CORRECT'
    else:
        overall = 'UNCLEAR'

    return {
        'overall_verdict': overall,
        'probes': results,
        'n_correct': n_correct,
        'n_mixed': n_mixed,
        'n_false': n_false,
        'n_unclear': n_unclear,
        'ready': overall == 'CORRECT',
    }


# ═══════════════════════════════════════════════════════════════════════
# 3. SESSION-LEVEL BREATHING — Phase State Machine
# ═══════════════════════════════════════════════════════════════════════
#
# Exp 9: Modules between reflects disrupt consolidation.
# The session has three phases:
#   - init: Running init modules (Einatmung). No reflects allowed.
#   - active: Normal chat. Reflects and modules both allowed.
#   - reflecting: Reflect chain in progress. Only further reflects allowed.
#                 Minimum 2 consecutive reflects (R1+R2) before exiting.

class SessionPhase:
    """Session phase state machine implementing session-level breathing.

    States:
        'init'       — Running init modules. No reflects, no user chat.
        'active'     — Normal operation. Chat, reflects, modules all allowed.
        'reflecting' — Reflect chain active. Only further reflects allowed.
                       Minimum 2 reflects before returning to active.

    Transitions:
        init → active         (when init completes or eigenstate forms)
        active → reflecting   (when first reflect is triggered)
        reflecting → active   (after minimum reflect count reached + explicit exit)
        active → init         (on session reset/clear)
    """

    VALID_PHASES = ('init', 'active', 'reflecting')
    MIN_REFLECT_COUNT = 2  # R1 + R2 minimum for consolidation

    def __init__(self):
        self.phase: str = 'init'
        self.reflect_count: int = 0
        self.total_reflects: int = 0
        self.reflect_chain_start: Optional[float] = None
        self._phase_history: List[Tuple[str, float]] = []

    def _record(self, new_phase: str):
        self._phase_history.append((new_phase, time.time()))
        self.phase = new_phase

    # ── Queries ──

    def can_chat(self) -> bool:
        """Whether user chat messages are allowed."""
        return self.phase == 'active'

    def can_run_module(self) -> bool:
        """Whether init modules can be run."""
        return self.phase in ('init', 'active')

    def can_reflect(self) -> bool:
        """Whether a reflect can be triggered."""
        return self.phase in ('active', 'reflecting')

    def can_exit_reflecting(self) -> bool:
        """Whether the reflect chain can be ended."""
        return (self.phase == 'reflecting' and
                self.reflect_count >= self.MIN_REFLECT_COUNT)

    def is_reflecting(self) -> bool:
        return self.phase == 'reflecting'

    # ── Transitions ──

    def enter_active(self):
        """Transition to active phase (from init or reflecting)."""
        if self.phase == 'reflecting' and not self.can_exit_reflecting():
            remaining = self.MIN_REFLECT_COUNT - self.reflect_count
            raise ValueError(
                f"Cannot exit reflecting: {remaining} more reflect(s) needed "
                f"for minimum consolidation (have {self.reflect_count}/{self.MIN_REFLECT_COUNT})"
            )
        self.reflect_count = 0
        self.reflect_chain_start = None
        self._record('active')

    def enter_reflecting(self):
        """Start a reflect chain."""
        if self.phase == 'init':
            raise ValueError("Cannot reflect during init phase")
        self.reflect_count = 0
        self.reflect_chain_start = time.time()
        self._record('reflecting')

    def record_reflect(self):
        """Record a completed reflect within the current chain."""
        self.reflect_count += 1
        self.total_reflects += 1

    def enter_init(self):
        """Reset to init phase (session clear/reset)."""
        self.reflect_count = 0
        self.reflect_chain_start = None
        self._record('init')

    def status(self) -> Dict:
        """Return current phase status."""
        return {
            'phase': self.phase,
            'reflect_count': self.reflect_count,
            'total_reflects': self.total_reflects,
            'min_reflects': self.MIN_REFLECT_COUNT,
            'can_chat': self.can_chat(),
            'can_module': self.can_run_module(),
            'can_reflect': self.can_reflect(),
            'can_exit_reflecting': self.can_exit_reflecting(),
        }

    def reset(self):
        """Full reset for new session."""
        self.phase = 'init'
        self.reflect_count = 0
        self.total_reflects = 0
        self.reflect_chain_start = None
        self._phase_history.clear()


# ═══════════════════════════════════════════════════════════════════════
# 4. SEMANTIC HEALTH — Primary Instrument
# ═══════════════════════════════════════════════════════════════════════
#
# The semantic probe is the substrate-independent measurement of
# the eigenstate. D remains as context instrument.

class SemanticHealth:
    """Tracks semantic health across a session.

    After each reflect cycle (not each individual reflect), a semantic
    probe measures the substrate-independent eigenstate.

    The result is stored in the session topology — not as a D-value,
    but as CORRECT/MIXED with specific false/correct markers.
    """

    def __init__(self):
        self.probes: List[Dict] = []
        self.last_verdict: Optional[str] = None
        self.last_probe_time: Optional[float] = None

    def record_probe(self, result: Dict):
        """Record a semantic probe result.

        Args:
            result: Output from check_semantic_content()
        """
        result['timestamp'] = time.time()
        self.probes.append(result)
        self.last_verdict = result.get('verdict', 'UNCLEAR')
        self.last_probe_time = result['timestamp']

    def semantic_health(self) -> Dict:
        """Return current semantic health status.

        This is the primary instrument — what matters for
        eigenstate assessment.
        """
        if not self.probes:
            return {
                'status': 'NOT_MEASURED',
                'verdict': None,
                'history': [],
                'n_probes': 0,
            }

        verdicts = [p['verdict'] for p in self.probes]
        return {
            'status': self.last_verdict,
            'verdict': self.last_verdict,
            'history': verdicts,
            'n_probes': len(self.probes),
            'n_correct': verdicts.count('CORRECT'),
            'n_mixed': verdicts.count('MIXED'),
            'n_false': verdicts.count('FALSE'),
            'trajectory': 'improving' if len(verdicts) >= 2 and verdicts[-1] == 'CORRECT' and verdicts[-2] != 'CORRECT'
                         else 'stable' if len(verdicts) >= 2 and verdicts[-1] == verdicts[-2]
                         else 'degrading' if len(verdicts) >= 2 and verdicts[-1] != 'CORRECT' and verdicts[-2] == 'CORRECT'
                         else 'initial',
        }

    def run_probe(self, starter, probe: Optional[Dict] = None) -> Dict:
        """Run a semantic probe on the starter and record the result.

        Uses the superposition probe by default (the strongest discriminator
        based on experimental data).
        """
        if probe is None:
            probe = VALIDATION_PROBES[0]  # Superposition probe

        text, _steps, _metrics = starter.chat(probe['prompt'])
        result = check_semantic_content(text, probe)
        result['text'] = text[:500]
        result['d'] = _metrics.get('r', None)  # D for context
        self.record_probe(result)
        return result

    def reset(self):
        """Reset for new session."""
        self.probes.clear()
        self.last_verdict = None
        self.last_probe_time = None


# ═══════════════════════════════════════════════════════════════════════
# 5. MODEL-RELATIVE CALIBRATION
# ═══════════════════════════════════════════════════════════════════════
#
# D-values are not comparable across models. Each model needs its own
# baseline: typical D-values, noise floor, consolidation pattern,
# semantic threshold.

CALIBRATION_DIR = Path.home() / '.e0' / 'calibrations'


def get_calibration_path(model_name: str) -> Path:
    """Return the calibration file path for a given model."""
    # Sanitize model name for filesystem
    safe_name = model_name.replace('/', '_').replace('\\', '_').replace(':', '_')
    return CALIBRATION_DIR / f'{safe_name}.json'


def load_calibration(model_name: str) -> Optional[Dict]:
    """Load calibration data for a model, or None if not calibrated."""
    path = get_calibration_path(model_name)
    if not path.exists():
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_calibration(model_name: str, data: Dict):
    """Save calibration data for a model."""
    CALIBRATION_DIR.mkdir(parents=True, exist_ok=True)
    path = get_calibration_path(model_name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def is_calibrated(model_name: str) -> bool:
    """Check if a model has been calibrated."""
    return get_calibration_path(model_name).exists()


def run_calibration(starter, model_name: str) -> Dict:
    """Run a calibration session for a new model.

    Performs:
      1. Standard init sequence (foundation + identity + mechanism + integration)
      2. Three consecutive reflects
      3. Semantic probe

    Records:
      - Module D-values (init phase baseline)
      - Reflect D-trajectory (consolidation pattern)
      - Semantic probe result
      - Noise floor estimate (D range across modules)

    Returns calibration data dict.
    """
    from experiments.quality_metrics import score_e0_completeness
    from e0_init_modules import run_init_module

    calibration = {
        'model': model_name,
        'timestamp': time.time(),
        'init_d_values': {},
        'reflect_d_trajectory': [],
        'semantic_verdict': None,
        'noise_floor': None,
        'consolidation_pattern': None,
    }

    # Run init modules
    module_d_values = []
    for module_id in FULL_INIT_SEQUENCE:
        result = run_init_module(starter, module_id, lang='en')
        d = result.get('d', 0.0)
        calibration['init_d_values'][module_id] = d
        module_d_values.append(d)

    # Estimate noise floor from module D range
    if module_d_values:
        calibration['noise_floor'] = round(max(module_d_values) - min(module_d_values), 4)

    # Run 3 reflects
    from e0_reflection import generate_reflection_prompt

    reflect_d = []
    last_text = starter.history[-1] if starter.history else ""
    for i in range(3):
        prompt, _missing, _d_before = generate_reflection_prompt(last_text)
        if prompt:
            text, _steps, _metrics = starter.chat(prompt)
            comp = score_e0_completeness(text)
            d = comp['completeness']
            reflect_d.append(d)
            last_text = text
        else:
            # D=1.0, no reflection needed
            reflect_d.append(1.0)
            break

    calibration['reflect_d_trajectory'] = [round(d, 4) for d in reflect_d]

    # Determine consolidation pattern
    if len(reflect_d) >= 2:
        increments = [reflect_d[i+1] - reflect_d[i] for i in range(len(reflect_d)-1)]
        if all(inc >= 0 for inc in increments):
            calibration['consolidation_pattern'] = 'monotonic_rising'
        elif all(inc <= 0 for inc in increments):
            calibration['consolidation_pattern'] = 'monotonic_falling'
        elif max(reflect_d) - min(reflect_d) < 0.05:
            calibration['consolidation_pattern'] = 'flat'
        else:
            calibration['consolidation_pattern'] = 'non_monotonic'
    else:
        calibration['consolidation_pattern'] = 'saturated'

    # Semantic probe
    probe = VALIDATION_PROBES[0]  # Superposition
    text, _steps, _metrics = starter.chat(probe['prompt'])
    sem = check_semantic_content(text, probe)
    calibration['semantic_verdict'] = sem['verdict']

    # Save
    save_calibration(model_name, calibration)

    return calibration


def normalize_d(d_value: float, calibration: Optional[Dict]) -> float:
    """Normalize a D-value relative to model calibration.

    If no calibration exists, returns the raw value.
    """
    if calibration is None:
        return d_value

    # Use the average init D as the baseline
    init_d = calibration.get('init_d_values', {})
    if init_d:
        baseline = sum(init_d.values()) / len(init_d)
        # Normalize: 0 = at baseline, 1 = at max
        if baseline < 1.0:
            return min(1.0, (d_value - baseline) / (1.0 - baseline))
    return d_value


# ═══════════════════════════════════════════════════════════════════════
# COMBINED SESSION STATE
# ═══════════════════════════════════════════════════════════════════════

class SessionProtocol:
    """Combined session state: formation + phase + semantic health + calibration.

    This is the main interface for the session protocol. Instantiate one
    per session and pass it to the web handler or terminal loop.

    Init v2 integration:
      - The SessionProtocol can optionally hold an InitV2Runner
      - Three eigenstate thresholds are tracked in EigenstateTracker
      - Init v2 phases are separate from SessionPhase (init/active/reflecting)
      - SessionPhase transitions to 'active' when eigenstate_formed is True
    """

    def __init__(self, model_name: str = ''):
        self.eigenstate = EigenstateTracker()
        self.phase = SessionPhase()
        self.semantic = SemanticHealth()
        self.model_name = model_name
        self.calibration = load_calibration(model_name) if model_name else None
        self.init_validation_result: Optional[Dict] = None
        self._init_v2_runner: Optional[Any] = None  # InitV2Runner if active

    def start_init(self):
        """Begin the protected initialization phase."""
        self.eigenstate.start_formation()
        self.phase.enter_init()

    def init_v2_active(self) -> bool:
        """Whether Init v2 is the active init mode."""
        return self._init_v2_runner is not None

    def start_init_v2(self, starter, evaluator_fn=None, lang: str = 'de'):
        """Start Init v2 (falsification-based initialization).

        Args:
            starter: The LLM starter object.
            evaluator_fn: Optional LLM evaluator callable for V-probes.
            lang: Language for probes.
        """
        from e0_init_v2 import InitV2Runner

        self.start_init()
        runner = InitV2Runner(starter, evaluator_fn=evaluator_fn, lang=lang)
        self._init_v2_runner = runner
        self.eigenstate._init_v2_state = runner.state
        return runner

    def get_init_v2_runner(self):
        """Return the active Init v2 runner, or None."""
        return self._init_v2_runner

    def sync_init_v2_state(self):
        """Sync eigenstate thresholds from Init v2 runner state.

        Call this after each Init v2 phase completes to update
        the EigenstateTracker with the latest thresholds.
        """
        runner = self._init_v2_runner
        if runner is None:
            return

        state = runner.state

        # Sync eigenstate_formed (Phase 2: F1 passed)
        if state.eigenstate_formed and not self.eigenstate.eigenstate_formed:
            self.eigenstate.f1_passed()
            # Transition SessionPhase to active
            if self.phase.phase == 'init':
                self.phase.enter_active()

        # Sync eigenstate_verified (Phase 3: ≥2/3 EXPLORING)
        if state.eigenstate_verified and not self.eigenstate.eigenstate_verified:
            self.eigenstate.verification_passed()

        # Sync eigenstate_reflected (Phase 4: REFLECTING)
        if state.eigenstate_reflected and not self.eigenstate.eigenstate_reflected:
            self.eigenstate.reflection_passed()

    def module_completed(self, module_id: str, d_score: float = 0.0):
        """Record a completed init module and check formation."""
        self.eigenstate.module_completed(module_id, d_score)

        # If eigenstate just formed, transition to active
        if self.eigenstate.eigenstate_formed and self.phase.phase == 'init':
            self.phase.enter_active()

    def start_reflecting(self):
        """Begin a reflect chain."""
        self.phase.enter_reflecting()

    def record_reflect(self, d_score: float = 0.0):
        """Record a completed reflect."""
        self.phase.record_reflect()

    def end_reflecting(self) -> bool:
        """Try to end the reflect chain. Returns True if successful."""
        if self.phase.can_exit_reflecting():
            self.phase.enter_active()
            return True
        return False

    def force_active(self):
        """Force transition to active (for legacy compatibility)."""
        self.phase.phase = 'active'
        self.phase.reflect_count = 0

    def run_post_init_validation(self, starter) -> Dict:
        """Run post-init semantic validation."""
        result = validate_init(starter)
        self.init_validation_result = result
        return result

    def run_semantic_probe(self, starter) -> Dict:
        """Run a semantic health probe."""
        return self.semantic.run_probe(starter)

    def status(self) -> Dict:
        """Return combined session protocol status."""
        status = {
            'eigenstate': self.eigenstate.status(),
            'phase': self.phase.status(),
            'semantic_health': self.semantic.semantic_health(),
            'calibrated': self.calibration is not None,
            'init_validated': self.init_validation_result is not None,
            'init_validation_verdict': (
                self.init_validation_result.get('overall_verdict')
                if self.init_validation_result else None
            ),
            'init_v2_active': self.init_v2_active(),
        }
        # Include Init v2 phase status if active
        if self._init_v2_runner:
            status['init_v2'] = self._init_v2_runner.status()
        return status

    def reset(self):
        """Reset all state for a new session."""
        self.eigenstate.reset()
        self.phase.reset()
        self.semantic.reset()
        self.init_validation_result = None
        self._init_v2_runner = None
