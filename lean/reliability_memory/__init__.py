"""
reliability_memory — lean E₀ reliability-memory core.

Zero third-party dependencies.  `mcp` is optional (see mcp_server.py).
"""
from .primitives import Edge, Outcome
from .traces import Traces
from .store import ReliabilityStore, RecommendResult

__all__ = ["Edge", "Outcome", "Traces", "ReliabilityStore", "RecommendResult"]
