"""Shared pytest fixtures for e0_controller test suite."""

import pytest

from e0_controller.primitives import Edge, Outcome
from e0_controller.landscape import Landscape


# ---------------------------------------------------------------------------
# Common execute_fn mocks
# ---------------------------------------------------------------------------

@pytest.fixture
def success_fn():
    """Execute function that always returns SUCCESS."""
    return lambda s, t: Outcome.SUCCESS


@pytest.fixture
def failure_fn():
    """Execute function that always returns FAILURE."""
    return lambda s, t: Outcome.FAILURE


# ---------------------------------------------------------------------------
# Minimal landscapes for quick tests
# ---------------------------------------------------------------------------

@pytest.fixture
def empty_landscape():
    """Empty Landscape with no states or edges."""
    return Landscape()


@pytest.fixture
def linear_landscape():
    """A → B → C linear landscape (delta=1.0, resistance=1.0)."""
    L = Landscape()
    for s in ["A", "B", "C"]:
        L.add_state(s)
    L.add_edge("A", "B", delta=1.0, resistance=1.0)
    L.add_edge("B", "C", delta=1.0, resistance=1.0)
    return L


@pytest.fixture
def diamond_landscape():
    """Diamond: A → B, A → C, B → D, C → D."""
    L = Landscape()
    for s in ["A", "B", "C", "D"]:
        L.add_state(s)
    L.add_edge("A", "B", delta=1.0, resistance=1.0)
    L.add_edge("A", "C", delta=1.0, resistance=1.0)
    L.add_edge("B", "D", delta=1.0, resistance=1.0)
    L.add_edge("C", "D", delta=1.0, resistance=1.0)
    return L
