"""
E₀ Reflexive Action (C49)
==========================
Closes the reflexive loop: diagnosis → action.

C47 (Dual Reflection) diagnoses component health and produces
deactivation_candidates + meta_actions as text. This module
converts those diagnoses into concrete, reversible landscape
mutations and applies them.

Canon basis:
    reflexivitaet (L7): "Emerges when system models own transition
    structure, self-modification becomes admissible transition,
    historization constrains future self-changes."

    AGI Blueprint §5: "Self-modification becomes one admissible
    transition among others."

The key constraint: only modulation flags can be toggled (curvature,
overlap). Core components are NEVER deactivated — this mirrors the
canon's distinction between contingent modulation and necessary
structural primitives.

Usage:
    from e0_controller.reflexive_action import (
        apply_reflexive_actions, ReflexiveActionResult,
    )

    # After dual reflection:
    result = apply_reflexive_actions(dual_report, landscape)
    # result.actions_taken: what was changed
    # result.restore(): undo everything
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .dual_reflection import DualReflectionReport, SelfGraphDiagnosis
from .landscape import Landscape


# ──────────────────────────────────────────────
# 1. Modulation flag map
# ──────────────────────────────────────────────

# Maps deactivation candidate names → landscape attribute names.
# Only modulation components are allowed targets.
_MODULATION_FLAGS: Dict[str, str] = {
    "curvature": "curvature_modulation",
    "overlap": "overlap_modulation",
}


# ──────────────────────────────────────────────
# 2. Data structures
# ──────────────────────────────────────────────

@dataclass
class ReflexiveAction:
    """A single reflexive self-modification."""
    component: str          # e.g. "curvature"
    flag_name: str          # e.g. "curvature_modulation"
    old_value: bool         # value before action
    new_value: bool         # value after action
    reason: str             # human-readable rationale

    @property
    def is_deactivation(self) -> bool:
        return self.old_value and not self.new_value


@dataclass
class ReflexiveActionResult:
    """Result of applying reflexive actions to a landscape."""
    actions_taken: List[ReflexiveAction] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)  # candidates already inactive

    @property
    def any_changes(self) -> bool:
        return len(self.actions_taken) > 0

    def restore(self, landscape: Landscape) -> int:
        """Undo all actions — restore original modulation state.

        Returns the number of flags restored.
        """
        count = 0
        for a in reversed(self.actions_taken):
            setattr(landscape, a.flag_name, a.old_value)
            count += 1
        return count

    def summary(self) -> str:
        """Human-readable summary of what happened."""
        if not self.actions_taken and not self.skipped:
            return "No reflexive actions needed."
        lines = []
        for a in self.actions_taken:
            verb = "Deactivated" if a.is_deactivation else "Reactivated"
            lines.append(f"  {verb} {a.component} ({a.reason})")
        for s in self.skipped:
            lines.append(f"  Skipped {s} (already inactive)")
        return "\n".join(lines)


# ──────────────────────────────────────────────
# 3. Core logic
# ──────────────────────────────────────────────

def plan_reflexive_actions(
    diagnosis: SelfGraphDiagnosis,
    landscape: Landscape,
) -> List[ReflexiveAction]:
    """Plan reflexive actions from a self-graph diagnosis.

    Only deactivation of harmful modulation components is planned.
    Components that are already inactive are skipped (reported in result).

    Returns a list of planned actions (not yet applied).
    """
    actions = []
    for candidate in diagnosis.deactivation_candidates:
        flag_name = _MODULATION_FLAGS.get(candidate)
        if flag_name is None:
            # Unknown component — not a modulation flag. Skip.
            continue
        current = getattr(landscape, flag_name, False)
        if not current:
            # Already inactive — no action needed.
            continue
        # Find the assessment for context
        assessment = next(
            (c for c in diagnosis.components if c.name == candidate),
            None,
        )
        reason = (
            f"quality={assessment.quality:+.3f}, load={assessment.load:.1f}"
            if assessment else "harmful modulation"
        )
        actions.append(ReflexiveAction(
            component=candidate,
            flag_name=flag_name,
            old_value=True,
            new_value=False,
            reason=reason,
        ))
    return actions


def apply_reflexive_actions(
    report: DualReflectionReport,
    landscape: Landscape,
) -> ReflexiveActionResult:
    """Apply reflexive self-modifications based on dual reflection.

    This is the function that closes the reflexive loop:
    1. Reads deactivation_candidates from the diagnosis
    2. Plans flag changes for modulation components
    3. Applies them to the landscape
    4. Returns a result with undo capability

    Only modulation components (curvature, overlap) can be toggled.
    Core components are structurally protected.
    """
    diagnosis = report.self_diagnosis
    planned = plan_reflexive_actions(diagnosis, landscape)

    result = ReflexiveActionResult()

    # Track already-inactive candidates as skipped
    for candidate in diagnosis.deactivation_candidates:
        flag_name = _MODULATION_FLAGS.get(candidate)
        if flag_name is not None and not getattr(landscape, flag_name, False):
            result.skipped.append(candidate)

    # Apply planned actions
    for action in planned:
        setattr(landscape, action.flag_name, action.new_value)
        result.actions_taken.append(action)

    return result


# ──────────────────────────────────────────────
# 4. Reflexive Journal — Stufe 4b Representation
# ──────────────────────────────────────────────

@dataclass
class ReflexiveJournalEntry:
    """One recorded reflexive action with iteration context."""
    iteration: int
    action: ReflexiveAction
    restored: bool = False


class ReflexiveJournal:
    """Persistent chronological record of all reflexive self-modifications.

    This is the Stufe 4b representation: the system's self-modification
    history, available for exposition to external observers (LLM, user).

    Canon basis (Bridge 4, Stufe 4b): "In welchem Raum wird die
    Self-Structure dargestellt?" Answer: as a chronological journal
    of concrete, reversible actions with rationale.
    """

    def __init__(self) -> None:
        self._entries: List[ReflexiveJournalEntry] = []

    def record(self, result: ReflexiveActionResult, iteration: int) -> int:
        """Record all actions from a ReflexiveActionResult.

        Returns the number of entries recorded.
        """
        count = 0
        for action in result.actions_taken:
            self._entries.append(ReflexiveJournalEntry(
                iteration=iteration,
                action=action,
            ))
            count += 1
        return count

    def mark_restored(self, iteration: int) -> int:
        """Mark all actions from a given iteration as restored.

        Returns the number of entries marked.
        """
        count = 0
        for e in self._entries:
            if e.iteration == iteration and not e.restored:
                e.restored = True
                count += 1
        return count

    @property
    def entries(self) -> List[ReflexiveJournalEntry]:
        """All recorded entries (copy)."""
        return list(self._entries)

    @property
    def active_deactivations(self) -> List[ReflexiveJournalEntry]:
        """Deactivation actions still in effect (not restored)."""
        return [
            e for e in self._entries
            if not e.restored and e.action.is_deactivation
        ]

    @property
    def total_actions(self) -> int:
        return len(self._entries)

    @property
    def active_count(self) -> int:
        return len(self.active_deactivations)

    def current_state(self) -> List[Tuple[str, bool]]:
        """Current modulation state implied by journal.

        Returns list of (component, is_active) tuples for components
        that have been acted on. Tracks net effect: if deactivated
        then restored, it's active again.
        """
        state: Dict[str, bool] = {}
        for e in self._entries:
            if e.restored:
                state[e.action.component] = e.action.old_value
            else:
                state[e.action.component] = e.action.new_value
        return sorted(state.items())

    def format(self) -> str:
        """Human-readable chronological history."""
        if not self._entries:
            return "  No reflexive actions taken."
        lines = []
        for e in self._entries:
            status = "[restored]" if e.restored else "[active]"
            verb = "Deactivated" if e.action.is_deactivation else "Modified"
            lines.append(
                f"  Iteration {e.iteration}: {verb} {e.action.component} "
                f"({e.action.reason}) {status}"
            )
        return "\n".join(lines)
