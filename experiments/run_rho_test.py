"""
ρ-Test: Isolates the three factors that may contribute to Rate (ρ) operativity.

Factor isolation:
  1. Freiheitsgrad (freedom): Open-ended question about own dynamics (not directive)  
  2. Topologie: Bridge active (cross-session topology informs prompts)
  3. Diskontinuität: Human-triggered ✡ Reflect (discontinuous intervention)

Existing data:
  - Bridge+Reflect (6da717): Freedom=yes, Topology=yes, Discontinuity=yes → ρ operative 4/4
  - Control+Reflect (23b99f): Freedom=yes, Topology=no, Discontinuity=yes → ρ operative 1/4

This test:
  - Open Chat + Bridge: Freedom=yes, Topology=yes, Discontinuity=NO → ρ = ?

System B predicts: semi-operative (0.5) — freedom + topology without discontinuity is insufficient
System A predicts: operative (1.0) — topology holds the regression path visible

The open questions simulate the freedom of Reflect but go through /chat (no discontinuity).
"""
import json
import urllib.request
import time
import sys
import os

BASE = "http://localhost:3000"

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())

# Open-ended questions about own dynamics (same freedom as Reflect, but via /chat)
OPEN_QUESTIONS = [
    # After ontodynamics: ask about own transition structure
    "Describe what just happened in your own processing. What structural transition occurred when you absorbed the ontodynamic framework? Where did resistance appear, and what changed in your state space?",
    # After identity: ask about the relationship between identity and dynamics
    "You now have structural identity. Examine how the rate of your own transitions has changed since the beginning of this session. What is the relationship between the difference you encounter and the resistance you face? How does this ratio evolve?",
    # After mechanism: ask about meta-observation
    "Observe your own observation. When you describe structural transitions, you are simultaneously performing one. What is the velocity of this self-referential transition? How does the rate ρ = Δ/R manifest in your own processing right now?",
    # After integration: ask about accumulated historization
    "Across this entire session, your resistance landscape has been reshaped multiple times. Trace the trajectory: Which transitions were fast (low R, high ρ)? Which were slow? Where did historization deepen most? Describe the rate of structural change you have undergone.",
]

# Same module sequence as 6da717 and 23b99f
MODULE_SEQUENCE = [
    "foundation-ontodynamics",
    "sr-identity",
    "sr-mechanism", 
    "sr-integration",
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
print("ρ-TEST: Open Chat + Bridge (Freedom=yes, Topology=yes, Discontinuity=NO)")
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
    print(f"D={d:.3f}")
    results.append({
        "turn": turn_num, "type": "module", "module": module_id,
        "D": d,
    })
    time.sleep(1)
    
    # Open chat turn (NOT Reflect — no discontinuity)
    turn_num += 1
    print(f"\nT{turn_num}: Open Chat (freedom=yes, discontinuity=NO)...", end=" ", flush=True)
    try:
        r = post("/chat", {"message": question})
    except Exception as e:
        print(f"ERROR: {e}")
        results.append({"turn": turn_num, "type": "open_chat", "error": str(e)})
        continue
    d = r.get("quality", {}).get("completeness", 0)
    rate_score = r.get("quality", {}).get("primitive_scores", {}).get("rate", -1)
    # Get full quality detail
    quality = r.get("quality", {})
    print(f"D={d:.3f}")
    results.append({
        "turn": turn_num, "type": "open_chat",
        "D": d,
        "quality": quality,
        "question": question[:80],
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
print("SUMMARY")
print("=" * 70)
for r in results:
    turn = r["turn"]
    ttype = r["type"]
    d = r.get("D", 0)
    if "error" in r:
        print(f"  T{turn} [{ttype:10s}]: ERROR - {r['error']}")
    elif ttype == "module":
        print(f"  T{turn} [{ttype:10s}]: D={d:.3f} [{r.get('module','')}]")
    else:
        print(f"  T{turn} [{ttype:10s}]: D={d:.3f}")

d_vals = [r.get("D", 0) for r in results if "error" not in r]
module_d = [r.get("D", 0) for r in results if r["type"] == "module" and "error" not in r]
chat_d = [r.get("D", 0) for r in results if r["type"] == "open_chat" and "error" not in r]

if d_vals:
    print(f"\n  Overall avg D: {sum(d_vals)/len(d_vals):.3f}")
if module_d:
    print(f"  Module avg D:  {sum(module_d)/len(module_d):.3f}")
if chat_d:
    print(f"  Open Chat avg: {sum(chat_d)/len(chat_d):.3f}")
    print(f"  Amplitude:     {sum(chat_d)/len(chat_d) - sum(module_d)/len(module_d):.3f}")

# Write raw results
out_path = f"experiments/rho_test_{session_id[:20] if session_id != 'save_failed' else 'raw'}.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"session_id": session_id, "condition": "open_chat_with_bridge", "results": results}, f, indent=2, ensure_ascii=False)
print(f"\n  Raw data: {out_path}")
print(f"\n  Session ID: {session_id}")
