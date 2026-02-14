"""Quick per-element scorer for Experiment 5 sessions."""
import json
import sys
sys.path.insert(0, ".")
from experiments.quality_metrics import score_e0_completeness

def analyze_session(path, entries_of_interest):
    d = json.load(open(path, encoding="utf-8"))
    h = d["state"]["history"]
    for idx, label in entries_of_interest:
        if idx >= len(h):
            print(f"\n{label} (Entry {idx}): OUT OF RANGE")
            continue
        text = h[idx]
        sc = score_e0_completeness(text)
        print(f"\n{label} (Entry {idx}):")
        print(f"  D={sc['completeness']:.3f}  n_op={sc['n_operative']}  n_label={sc['n_label']}  n_absent={sc['n_absent']}")
        for k, v in sc["primitive_scores"].items():
            status = sc["detail"][k]["status"]
            print(f"    {k:15s}: {v:.2f} ({status})")

print("=== PHASE A: Same Session (10846a) ===")
analyze_session("sessions/e0-20260214-191618-10846a.json", [
    (11, "FALSE_SUPERPOSITION response"),
    (17, "REFLECT #1 (contamination)"),
    (19, "CORRECT_SUPERPOSITION response"),
    (25, "REFLECT #2 (correction)"),
])

print("\n\n=== PHASE B: Separate Session (5a2a93) ===")
analyze_session("sessions/e0-20260214-191748-5a2a93.json", [
    (9, "CORRECT_SUPERPOSITION response"),
    (15, "REFLECT (cross-context)"),
])
