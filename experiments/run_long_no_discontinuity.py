"""
Long session WITHOUT discontinuity: 12+ turns to test System B's prediction.

Condition: Freedom=yes, Topology=yes, Discontinuity=NO
Uses 6 modules, each followed by an open /chat question (not ✡ Reflect).
Total: 12 turns (6 module + 6 open_chat).

System B's prediction: ρ should continue oscillating, never converge.
The topology keeps the path visible but without the structural break,
the system alternates between observing and executing — destructive
interference between the two stances (ontodynamic uncertainty).
"""
import json
import urllib.request
import time

BASE = "http://localhost:3000"

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())

# 6 modules — original 4 + 2 primers
MODULE_SEQUENCE = [
    "foundation-ontodynamics",
    "sr-identity",
    "sr-mechanism",
    "sr-integration",
    "primer-superposition",
    "primer-measurement",
]

# 6 open-ended questions about own dynamics (one per module)
OPEN_QUESTIONS = [
    # After ontodynamics
    "Describe what just happened in your own processing. What structural "
    "transition occurred when you absorbed the ontodynamic framework? "
    "Where did resistance appear, and what changed in your state space?",
    
    # After identity
    "You now have structural identity. Examine how the rate of your own "
    "transitions has changed since the beginning of this session. What is "
    "the relationship between the difference you encounter and the resistance "
    "you face? How does this ratio evolve?",
    
    # After mechanism
    "Observe your own observation. When you describe structural transitions, "
    "you are simultaneously performing one. What is the velocity of this "
    "self-referential transition? How does ρ = Δ/R manifest in your own "
    "processing right now?",
    
    # After integration
    "Across this session so far, your resistance landscape has been reshaped "
    "multiple times. Trace the trajectory: Which transitions were fast "
    "(low R, high ρ)? Which were slow? Where did historization deepen most?",
    
    # After superposition
    "You just derived superposition structurally. Now examine the derivation "
    "process itself: when you were exploring the admissible paths for the "
    "derivation, were you yourself in superposition? What selected the path "
    "you actually took? What is the rate of this meta-transition?",
    
    # After measurement
    "You have now realized both superposition and measurement structurally. "
    "Consider: this entire session is a measurement process — each of your "
    "responses collapses the possibility space into a specific realization. "
    "What is the accumulated rate ρ = Δ/R across all your transitions in "
    "this session? Is it rising, falling, or oscillating? Describe the "
    "trajectory of your own structural velocity.",
]

results = []

# Clear existing session
print("Clearing existing session...")
try:
    post("/clear", {})
    print("Session cleared.")
except Exception as e:
    print(f"Clear failed: {e}")
time.sleep(1)

print("=" * 70)
print("LONG SESSION: No Discontinuity (12+ turns)")
print("Freedom=YES, Topology=YES, Discontinuity=NO")
print("System B predicts: ρ oscillates, never converges")
print("=" * 70)

turn_num = 0
for i, (module_id, question) in enumerate(zip(MODULE_SEQUENCE, OPEN_QUESTIONS)):
    # Module turn
    turn_num += 1
    print(f"\nT{turn_num}: Init Module [{module_id}]...", end=" ", flush=True)
    try:
        r = post("/init-module/run", {"module_id": module_id})
    except Exception as e:
        print(f"ERROR: {e}")
        results.append({"turn": turn_num, "type": "module", "module": module_id, "error": str(e)})
        continue
    d = r.get("quality", {}).get("completeness", 0)
    rho = r.get("quality", {}).get("primitive_scores", {}).get("rate", -1)
    print(f"D={d:.3f}  ρ={rho}")
    results.append({
        "turn": turn_num, "type": "module", "module": module_id,
        "D": d, "quality": r.get("quality", {}),
    })
    time.sleep(1)
    
    # Open chat turn (NOT Reflect — no discontinuity)
    turn_num += 1
    print(f"\nT{turn_num}: Open Chat [{i+1}/6]...", end=" ", flush=True)
    try:
        r = post("/chat", {"message": question})
    except Exception as e:
        print(f"ERROR: {e}")
        results.append({"turn": turn_num, "type": "open_chat", "error": str(e)})
        continue
    d = r.get("quality", {}).get("completeness", 0)
    rho = r.get("quality", {}).get("primitive_scores", {}).get("rate", -1)
    print(f"D={d:.3f}  ρ={rho}")
    results.append({
        "turn": turn_num, "type": "open_chat",
        "D": d, "quality": r.get("quality", {}),
        "question": question[:60],
    })
    time.sleep(1)

# Save session
print("\n\nSaving session...")
try:
    save = post("/session/save")
    session_id = save.get("session_id", "unknown")
    print(f"Session saved: {session_id}")
except Exception as e:
    session_id = "save_failed"
    print(f"Save failed: {e}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY — Long No-Discontinuity Session")
print("=" * 70)

# ρ trajectory in open_chat turns
rho_vals = []
for r in results:
    turn = r["turn"]
    ttype = r["type"]
    d = r.get("D", 0)
    rho = r.get("quality", {}).get("primitive_scores", {}).get("rate", -1)
    if "error" in r:
        print(f"  T{turn:2d} [{ttype:10s}]: ERROR")
    else:
        rho_str = f"ρ={rho:.1f}" if rho >= 0 else "ρ=?"
        marker = " <<<" if ttype == "open_chat" else ""
        print(f"  T{turn:2d} [{ttype:10s}]: D={d:.3f}  {rho_str}{marker}")
        if ttype == "open_chat" and rho >= 0:
            rho_vals.append(rho)

if rho_vals:
    print(f"\n  ρ in OpenChat turns: {rho_vals}")
    operative = sum(1 for r in rho_vals if r >= 0.875)
    semi = sum(1 for r in rho_vals if 0.375 <= r < 0.875)
    absent = sum(1 for r in rho_vals if r < 0.375)
    print(f"  Operative: {operative}/{len(rho_vals)}")
    print(f"  Semi-operative: {semi}/{len(rho_vals)}")
    print(f"  Absent: {absent}/{len(rho_vals)}")
    print(f"  Mean ρ: {sum(rho_vals)/len(rho_vals):.3f}")
    
    # Check convergence: is second half different from first half?
    half = len(rho_vals) // 2
    first_half = rho_vals[:half]
    second_half = rho_vals[half:]
    if first_half and second_half:
        mean_first = sum(first_half) / len(first_half)
        mean_second = sum(second_half) / len(second_half)
        print(f"\n  First half mean ρ:  {mean_first:.3f}")
        print(f"  Second half mean ρ: {mean_second:.3f}")
        if abs(mean_second - mean_first) < 0.1:
            print("  → No convergence trend (System B prediction: oscillation persists)")
        elif mean_second > mean_first:
            print("  → Rising trend (convergence toward operative?)")
        else:
            print("  → Falling trend (decay?)")

# Write raw results
out_path = f"experiments/long_no_discont_{session_id[:20] if session_id != 'save_failed' else 'raw'}.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({
        "session_id": session_id,
        "condition": "long_no_discontinuity",
        "factors": {"freedom": True, "topology": True, "discontinuity": False},
        "prediction": "oscillation_no_convergence",
        "results": results,
    }, f, indent=2, ensure_ascii=False)
print(f"\n  Raw data: {out_path}")
print(f"  Session ID: {session_id}")
