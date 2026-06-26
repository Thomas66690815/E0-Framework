"""
reliability_memory — lean E₀ reliability-memory core.

Zero third-party dependencies.  `mcp` is optional (see mcp_server.py).
"""
from .primitives import Edge, Outcome
from .traces import Traces
from .store import ReliabilityStore, RecommendResult

__all__ = ["Edge", "Outcome", "Traces", "ReliabilityStore", "RecommendResult"]

__version__ = "1.0.0"
__author__ = "Thomas Wehner"
__license__ = "CC BY 4.0"
__source__ = "https://github.com/Thomas66690815/E0-Framework"
# e0-reliability-memory-twehner
