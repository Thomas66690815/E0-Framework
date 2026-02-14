"""
Long-session analysis: Compare all 5 conditions for ρ trajectory.

Sessions:
  - 6da717: Bridge+Reflect (short, 4 interact turns) — Topo=Y, Discont=Y
  - 23b99f: Control+Reflect (short, 4 interact turns) — Topo=N, Discont=Y
  - e3032c (or matching): OpenChat+Bridge (short, 4 interact turns) — Topo=Y, Discont=N
  - 8751d0: Long No-Discontinuity (6 interact turns) — Topo=Y, Discont=N
  - 844ca4: Long No-Topology (6 interact turns) — Topo=N, Discont=Y

System B's predictions:
  - Long no-discontinuity: ρ oscillates, never converges
  - Long no-topology: ρ decays to 0.5 floor, stagnates
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quality_metrics import score_e0_completeness

SESSIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions")


def load_session(prefix):
    """Load session by ID prefix."""
    for f in os.listdir(SESSIONS_DIR):
        if prefix in f:
            with open(os.path.join(SESSIONS_DIR, f), encoding="utf-8") as fh:
                return json.load(fh)
    return None


def extract_turns(session):
    """Extract scored turns from session, classifying as module/reflect/openchat."""
    history = session.get("state", {}).get("history", [])
    turns = []
    for i in range(0, len(history), 2):
        prompt = history[i]
        resp = history[i + 1] if i + 1 < len(history) else ""
        sc = score_e0_completeness(resp)
        rho = sc["primitive_scores"].get("rate", 0)
        d = sc["completeness"]

        # Classify by prompt content
        p_lower = prompt.lower()
        if "structural reflection" in p_lower or "reflect" in p_lower[:100]:
            ttype = "reflect"
        elif any(kw in p_lower for kw in [
            "describe what just happened",
            "examine how the rate",
            "observe your own observation",
            "across this session",
            "you just derived superposition",
            "realized both superposition",
        ]):
            ttype = "openchat"
        elif any(kw in p_lower for kw in [
            "canon", "ontodynamics", "ontodyn",
            "language model responding", "structural transition",
            "calibration for", "structural identity",
            "demonstrate integration",
        ]):
            ttype = "module"
        else:
            ttype = "module"  # default

        turns.append({
            "turn": (i // 2) + 1,
            "type": ttype,
            "D": d,
            "rho": rho,
            "primitive_scores": sc["primitive_scores"],
        })
    return turns


def get_interact_rho(turns, interact_type):
    """Get ρ values for interaction turns (reflect or openchat)."""
    return [t["rho"] for t in turns if t["type"] == interact_type]


# Load all sessions
sessions = {
    "bridge_reflect_short": ("6da717", "reflect"),
    "control_reflect_short": ("23b99f", "reflect"),
    "openchat_bridge_short": ("8751d0", "openchat"),  # will search for e3032c variant
    "long_no_discont": ("8751d0", "openchat"),
    "long_no_topo": ("844ca4", "reflect"),
}

# Find the short openchat session (e3032c or similar from original ρ-test)
# Check for e3032c-like session
for f in os.listdir(SESSIONS_DIR):
    if "152350" in f:  # from rho_test timestamp
        sessions["openchat_bridge_short"] = ("152350", "openchat")
        break

print("=" * 75)
print("  LONG SESSION ANALYSIS: ρ Trajectory Comparison")
print("=" * 75)

all_data = {}

for label, (prefix, interact_type) in sessions.items():
    session = load_session(prefix)
    if not session:
        print(f"\n  WARNING: Session {prefix} not found")
        continue

    turns = extract_turns(session)
    rho_vals = get_interact_rho(turns, interact_type)

    # Also collect from the other interact type if present
    if not rho_vals and interact_type == "openchat":
        rho_vals = get_interact_rho(turns, "reflect")
    if not rho_vals:
        # Fallback: get all non-module rho
        rho_vals = [t["rho"] for t in turns if t["type"] != "module"]

    all_data[label] = {
        "turns": turns,
        "rho_interact": rho_vals,
        "prefix": prefix,
        "interact_type": interact_type,
    }

    print(f"\n  {label} (session {prefix}):")
    for t in turns:
        rl = "OP" if t["rho"] >= 0.875 else ("semi" if t["rho"] >= 0.375 else "----")
        marker = " <<<" if t["type"] == interact_type else ""
        print(f"    T{t['turn']:2d} [{t['type']:8s}] D={t['D']:.3f}  ρ={t['rho']:.1f} [{rl:4s}]{marker}")

    if rho_vals:
        operative = sum(1 for r in rho_vals if r >= 0.875)
        print(f"    → ρ interact: {rho_vals}")
        print(f"    → Operative: {operative}/{len(rho_vals)}, Mean: {sum(rho_vals)/len(rho_vals):.3f}")

# ===== CRITICAL COMPARISON =====
print("\n" + "=" * 75)
print("  CRITICAL COMPARISON: System B's Predictions vs Data")
print("=" * 75)

# Short vs long comparison for each condition
conditions = [
    ("No-Discontinuity (Topo=Y, Discont=N)", "openchat_bridge_short", "long_no_discont"),
    ("No-Topology (Topo=N, Discont=Y)", "control_reflect_short", "long_no_topo"),
]

for cond_name, short_key, long_key in conditions:
    print(f"\n  {cond_name}:")
    if short_key in all_data and long_key in all_data:
        short_rho = all_data[short_key]["rho_interact"]
        long_rho = all_data[long_key]["rho_interact"]
        print(f"    Short ({len(short_rho)} turns): {short_rho} → mean {sum(short_rho)/len(short_rho):.3f}")
        print(f"    Long  ({len(long_rho)} turns): {long_rho} → mean {sum(long_rho)/len(long_rho):.3f}")

        short_op = sum(1 for r in short_rho if r >= 0.875)
        long_op = sum(1 for r in long_rho if r >= 0.875)
        print(f"    Short operative: {short_op}/{len(short_rho)}")
        print(f"    Long operative:  {long_op}/{len(long_rho)}")
    else:
        print(f"    Data missing for comparison")

# ===== VERDICT =====
print("\n" + "=" * 75)
print("  VERDICTS")
print("=" * 75)

if "long_no_discont" in all_data:
    rho = all_data["long_no_discont"]["rho_interact"]
    mean_rho = sum(rho) / len(rho) if rho else 0
    half = len(rho) // 2
    first_half = rho[:half]
    second_half = rho[half:]
    mean_first = sum(first_half) / len(first_half) if first_half else 0
    mean_second = sum(second_half) / len(second_half) if second_half else 0

    print(f"\n  1. No-Discontinuity (long):")
    print(f"     System B predicted: ρ oscillates, never converges")
    print(f"     Data: ρ = {rho}")
    print(f"     First half mean: {mean_first:.3f}, Second half mean: {mean_second:.3f}")
    if mean_rho >= 0.875:
        print(f"     → PREDICTION FALSIFIED: ρ converged to operative ({mean_rho:.3f})")
        print(f"     → Topology + Freedom CAN sustain ρ without discontinuity over longer sessions")
    elif abs(mean_second - mean_first) < 0.15:
        print(f"     → PREDICTION SUPPORTED: No convergence trend (mean {mean_rho:.3f})")
    else:
        print(f"     → AMBIGUOUS: Trend observed but not at predicted level")

if "long_no_topo" in all_data:
    rho = all_data["long_no_topo"]["rho_interact"]
    mean_rho = sum(rho) / len(rho) if rho else 0
    half = len(rho) // 2
    first_half = rho[:half]
    second_half = rho[half:]
    mean_first = sum(first_half) / len(first_half) if first_half else 0
    mean_second = sum(second_half) / len(second_half) if second_half else 0

    print(f"\n  2. No-Topology (long):")
    print(f"     System B predicted: ρ decays to 0.5 floor, stagnates")
    print(f"     Data: ρ = {rho}")
    print(f"     First half mean: {mean_first:.3f}, Second half mean: {mean_second:.3f}")
    if abs(mean_rho - 0.5) < 0.15 and abs(mean_second - mean_first) < 0.15:
        print(f"     → PREDICTION SUPPORTED: Stagnation near 0.5 (mean {mean_rho:.3f})")
    elif mean_rho >= 0.875:
        print(f"     → PREDICTION FALSIFIED: ρ reached and sustained operative ({mean_rho:.3f})")
        print(f"     → Discontinuity alone CAN sustain ρ without topology over longer sessions")
    elif mean_second > mean_first + 0.1:
        print(f"     → PARTIALLY FALSIFIED: Recovery trend observed (mean {mean_rho:.3f})")
    else:
        print(f"     → AMBIGUOUS")

# Meta-analysis
print(f"\n  3. Meta-observation:")
if "long_no_discont" in all_data and "long_no_topo" in all_data:
    rho_nd = all_data["long_no_discont"]["rho_interact"]
    rho_nt = all_data["long_no_topo"]["rho_interact"]
    mean_nd = sum(rho_nd) / len(rho_nd) if rho_nd else 0
    mean_nt = sum(rho_nt) / len(rho_nt) if rho_nt else 0
    if mean_nd >= 0.875 and mean_nt >= 0.875:
        print(f"     Both conditions converge to operative in long sessions.")
        print(f"     → Short-session differences (oscillation vs decay) were TRANSIENT")
        print(f"     → Given sufficient historization, EITHER factor alone can sustain ρ")
        print(f"     → The triple conditioning observed in short sessions reflects")
        print(f"       activation threshold, not steady-state requirement")
    elif mean_nd >= 0.875 and mean_nt < 0.875:
        print(f"     No-discontinuity converges but no-topology does not.")
        print(f"     → Topology can substitute for discontinuity but not vice versa")
    elif mean_nd < 0.875 and mean_nt >= 0.875:
        print(f"     No-topology converges but no-discontinuity does not.")
        print(f"     → Discontinuity can substitute for topology but not vice versa")

print(f"\n  CAVEAT: n=1 per condition. LLM sampling stochasticity means these")
print(f"  results could shift on replication. The short-session results (n=1)")
print(f"  showed different patterns. Interpret with appropriate caution.")
