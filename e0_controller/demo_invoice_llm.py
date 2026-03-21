"""
E₀ Demo — Invoice Processing with LLM Adapter
================================================
Demonstrates the full A3 Hybrid architecture:

    1. Python Controller: deterministic path selection via S_eff
    2. MemOS: persistent state management + LLM summary
    3. LLM Adapter: semantic execution of transitions

Usage:
    # With real API:
    python -m e0_controller.demo_invoice_llm

    # With mock (no API key needed):
    python -m e0_controller.demo_invoice_llm --mock

Requires OPENAI_API_KEY in .env or environment (unless --mock).
"""

from __future__ import annotations

import json
import os
import sys

from e0_controller.primitives import Outcome
from e0_controller.domain_invoice import build_invoice_landscape
from e0_controller.controller import E0Controller, RunTrace
from e0_controller.memory_os import E0MemoryOS, CanonRef
from e0_controller.llm_adapter import E0LLMAdapter, LLMConfig


# ──────────────────────────────────────────────
# Task descriptions for each invoice edge
# ──────────────────────────────────────────────

INVOICE_TASKS = {
    "RECEIVED→PDF_LOADED":
        "Load the incoming invoice PDF and verify it is a valid, readable document.",
    "PDF_LOADED→DATA_EXTRACTED":
        "Extract structured data from the invoice: vendor name, invoice number, "
        "date, line items, total amount. Use OCR if needed.",
    "DATA_EXTRACTED→CUSTOMER_FOUND":
        "Look up the vendor/customer in the internal database using the extracted "
        "name and tax ID. Confirm identity.",
    "CUSTOMER_FOUND→AMOUNT_OK":
        "Validate the invoice amount against the purchase order. Check for "
        "discrepancies beyond the 5% tolerance threshold.",
    "AMOUNT_OK→CONTRACT_MATCH":
        "Match the invoice to an active contract. Verify contract number, "
        "validity period, and agreed pricing terms.",
    "CONTRACT_MATCH→POLICY_OK":
        "Check the invoice against company policies: approval limits, "
        "duplicate detection, compliance requirements.",
    "POLICY_OK→APPROVED":
        "Final approval: all checks passed, invoice is cleared for payment.",
    # Error paths
    "PDF_LOADED→REJECTED":
        "The PDF is corrupted or unreadable. Reject the invoice.",
    "DATA_EXTRACTED→HUMAN_REVIEW":
        "Extracted data is ambiguous or incomplete. Escalate to human reviewer.",
    "CUSTOMER_FOUND→HUMAN_REVIEW":
        "Customer match is ambiguous (multiple potential matches). "
        "Escalate to human reviewer.",
    "AMOUNT_OK→REJECTED":
        "Amount discrepancy exceeds tolerance. Reject the invoice.",
    "CONTRACT_MATCH→HUMAN_REVIEW":
        "No matching contract found or contract is expired. "
        "Escalate to human reviewer.",
    "POLICY_OK→REJECTED":
        "Policy violation detected. Reject the invoice.",
    # Recovery
    "HUMAN_REVIEW→CUSTOMER_FOUND":
        "Human reviewer has clarified the customer identity.",
    "HUMAN_REVIEW→DATA_EXTRACTED":
        "Human reviewer has corrected the extracted data.",
    "HUMAN_REVIEW→REJECTED":
        "Human reviewer has decided to reject the invoice.",
}


# ──────────────────────────────────────────────
# Mock LLM for --mock mode
# ──────────────────────────────────────────────

def mock_llm_call(system: str, user: str, config: LLMConfig) -> str:
    """Deterministic mock that simulates realistic invoice processing."""
    import json as _json

    # Check if this is an execute_transition call
    if "Execute the transition" in user:
        # Extract source → target from prompt
        if "CUSTOMER_FOUND" in user and "HUMAN_REVIEW" not in user:
            if "DATA_EXTRACTED" in user:
                # First attempt at customer lookup often fails
                return _json.dumps({
                    "outcome": "SUCCESS",
                    "result": "Customer 'Acme Corp' found in database (ID: C-4821). "
                              "Tax ID verified.",
                    "confidence": 0.92,
                })
        if "DATA_EXTRACTED" in user and "PDF_LOADED" in user:
            return _json.dumps({
                "outcome": "SUCCESS",
                "result": "Extracted: Vendor='Acme Corp', Invoice #INV-2026-0042, "
                          "Date=2026-03-15, Amount=€12,450.00, Tax ID=DE123456789.",
                "confidence": 0.88,
            })
        # Default: success
        return _json.dumps({
            "outcome": "SUCCESS",
            "result": "Transition completed successfully.",
            "confidence": 0.90,
        })

    # Default for other call types
    return _json.dumps({
        "delta": 0.4,
        "reasoning": "Moderate structural change.",
    })


# ──────────────────────────────────────────────
# Main Demo
# ──────────────────────────────────────────────

def run_demo(use_mock: bool = False):
    """Run the Invoice Domain demo with LLM adapter."""

    print("=" * 64)
    print("E₀ Controller — Invoice Processing Demo (Phase 3a)")
    print("=" * 64)

    # 1. Build landscape
    L = build_invoice_landscape()
    print(f"\nLandscape: {len(L.states)} states, {len(L.edges)} edges")

    # 2. Setup LLM adapter
    if use_mock:
        print("Mode: MOCK (no API calls)")
        adapter = E0LLMAdapter(call_fn=mock_llm_call)
    else:
        config = LLMConfig(model="gpt-4o-mini", temperature=0.2)
        adapter = E0LLMAdapter(config=config)
        print(f"Mode: LIVE (model={config.model})")

    # 3. Setup MemOS (persistent in memos/)
    memos_dir = os.path.join(os.getcwd(), "memos")
    os.makedirs(memos_dir, exist_ok=True)
    memos = E0MemoryOS(base_dir=memos_dir)
    print(f"MemOS: {memos_dir}")

    # 4. Create execute function with dynamic summary
    def make_summary_provider(memos_inst, landscape, sid):
        """Return a callable that generates a fresh MemOS summary per step."""
        def provider():
            try:
                ctx = memos_inst.load_context(sid)
                # Extract last state from runtime dict
                current = ctx.runtime.get("last_state", "RECEIVED") if ctx.runtime else "RECEIVED"
                return memos_inst.summarize_for_llm(ctx, current, landscape=landscape)
            except FileNotFoundError:
                return {}
        return provider

    session_id = "demo-invoice"
    summary_provider = make_summary_provider(memos, L, session_id)
    execute_fn = adapter.as_execute_fn(INVOICE_TASKS, summary_provider=summary_provider)

    # 5. Build controller
    ctrl = E0Controller(L, execute_fn)

    print(f"\nStarting: RECEIVED → APPROVED")
    print("-" * 64)

    # 6. Run controller
    trace = ctrl.run(start="RECEIVED", goal="APPROVED", max_cycles=15)

    # 7. Display results
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

    # 8. Save to MemOS (persistent)
    ctx = memos.snapshot_from_runtime(
        session_id,
        L, ctrl, trace,
        canon_refs=[CanonRef(
            name="ontodynamics",
            version="1.0",
            path="canon/ontodynamics.txt",
        )],
    )
    memos.save_context(ctx)
    memos.save_run(session_id, trace, goal="APPROVED")

    # 9. Show MemOS summary
    summary = memos.summarize_for_llm(ctx, trace.path[-1], landscape=L)
    print(f"\nMemOS Summary (final state = {trace.path[-1]}):")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    print(f"\nMemOS data persisted to: {memos_dir}")

    return trace


if __name__ == "__main__":
    use_mock = "--mock" in sys.argv
    run_demo(use_mock=use_mock)
