"""PeerBridge — adapts synchronous peer_fn to async human/API interaction.

The E0Controller's peer_fn is synchronous: (landscape, current, neighbors) → str.
For a human peer via WebSocket, we need to pause the controller and wait.

This module provides:
  - PeerBridge: blocks the controller coroutine until a response arrives
  - PeerRequest: the data sent to the peer
  - Timeout fallback to random selection (consistent with C81 insight)

Part of Layer B (Service Layer).  C83.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from e0_controller.landscape import Landscape
from e0_controller.snapshot_codec import encode_edge_info


@dataclass
class PeerRequest:
    """Data sent to a peer when E₀ is overloaded."""
    session_id: str
    current: str
    neighbors: List[str]
    edge_info: Dict[str, dict]   # per-target edge details
    overload_index: float
    tau: int                     # controller step counter


class PeerBridge:
    """Bridges synchronous peer_fn to async response handling.

    Usage in E0Session:
        bridge = PeerBridge(session_id="abc", timeout=60.0)
        controller = E0Controller(landscape, exec_fn, peer_fn=bridge.as_peer_fn())

    When the controller calls peer_fn, the bridge:
      1. Creates a PeerRequest
      2. Calls the registered on_request callback (e.g. WebSocket push)
      3. Waits for submit_response() to be called (e.g. from WebSocket handler)
      4. Returns the chosen target to the controller

    If no response within timeout, falls back to random selection.
    """

    def __init__(
        self,
        session_id: str,
        timeout: float = 60.0,
        on_request: Optional[Callable[[PeerRequest], None]] = None,
    ):
        self.session_id = session_id
        self.timeout = timeout
        self.on_request = on_request

        self._pending_event: Optional[asyncio.Event] = None
        self._pending_response: Optional[str] = None
        self._pending_request: Optional[PeerRequest] = None
        self._fallback_rng = random.Random(42)
        self._tau = 0

    def as_peer_fn(self) -> Callable:
        """Return a callable compatible with E0Controller's peer_fn signature.

        The returned function is synchronous from the controller's perspective.
        When called from within an asyncio event loop (via E0Session), it uses
        the event loop to wait for the async response.
        """
        def peer_fn(landscape: Landscape, current: str, neighbors: List[str]) -> Optional[str]:
            # Try to get the running event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No event loop — direct/sync mode (tests, CLI)
                return self._sync_peer(landscape, current, neighbors)

            # We're inside an async context — use the bridge mechanism
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                self._async_peer(landscape, current, neighbors),
                loop,
            )
            try:
                return future.result(timeout=self.timeout)
            except (concurrent.futures.TimeoutError, asyncio.TimeoutError):
                return self._fallback_rng.choice(neighbors)

        return peer_fn

    def _sync_peer(
        self, landscape: Landscape, current: str, neighbors: List[str]
    ) -> Optional[str]:
        """Synchronous fallback (no event loop). Returns random choice."""
        return self._fallback_rng.choice(neighbors)

    async def _async_peer(
        self, landscape: Landscape, current: str, neighbors: List[str]
    ) -> Optional[str]:
        """Async peer interaction — emit request, wait for response."""
        self._tau += 1
        edge_info = encode_edge_info(landscape, current, neighbors)

        request = PeerRequest(
            session_id=self.session_id,
            current=current,
            neighbors=list(neighbors),
            edge_info=edge_info,
            overload_index=0.0,  # will be set by E0Session if available
            tau=self._tau,
        )
        self._pending_request = request
        self._pending_event = asyncio.Event()
        self._pending_response = None

        # Notify subscriber (e.g. WebSocket handler)
        if self.on_request is not None:
            self.on_request(request)

        # Wait for response with timeout
        try:
            await asyncio.wait_for(self._pending_event.wait(), timeout=self.timeout)
        except asyncio.TimeoutError:
            self._pending_request = None
            return self._fallback_rng.choice(neighbors)

        response = self._pending_response
        self._pending_request = None

        # Validate response
        if response is not None and response in neighbors:
            return response
        # Invalid response — fall back
        return self._fallback_rng.choice(neighbors) if neighbors else None

    def submit_response(self, target: str) -> bool:
        """Called externally (e.g. from WebSocket handler) to provide peer's choice.

        Returns True if a pending request was resolved, False otherwise.
        """
        if self._pending_event is None or self._pending_event.is_set():
            return False
        self._pending_response = target
        self._pending_event.set()
        return True

    @property
    def is_waiting(self) -> bool:
        """True if the bridge is waiting for a peer response."""
        return (
            self._pending_event is not None
            and not self._pending_event.is_set()
        )

    @property
    def pending_request(self) -> Optional[PeerRequest]:
        """The current pending request, if any."""
        return self._pending_request if self.is_waiting else None
