"""
Automated session runner: Init-Reflect alternation with two-timescale bridge.
Calls the running E0 web server at localhost:3000.
Records D trajectory, bridge diagnostics, and Rate operative status.
"""
import json
import urllib.request
import time
import sys

BASE = "http://localhost:3000"

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())

def get(path):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as resp:
        return json.loads(resp.read().decode())

# Sequence: Ontodynamics → Reflect → Identity → Reflect → Mechanism → Reflect → Integration → Reflect
SEQUENCE = [
    ("module", "foundation-ontodynamics"),
    ("reflect", None),
    ("module", "sr-identity"),
    ("reflect", None),
    ("module", "sr-mechanism"),
    ("reflect", None),
    ("module", "sr-integration"),
    ("reflect", None),
]

results = []

# Clear any existing session first
print("Clearing existing session...")
try:
    post("/clear", {})
    print("Session cleared.")
except Exception as e:
    print(f"Clear failed (may be fine): {e}")
time.sleep(1)

print("=" * 70)
print("E0 Bridge Session — Init-Reflect Alternation")
print("=" * 70)

for i, (action, module_id) in enumerate(SEQUENCE, 1):
    turn_label = f"T{i}"
    if action == "module":
        print(f"\n{turn_label}: Init Module [{module_id}]...", end=" ", flush=True)
        try:
            r = post("/init-module/run", {"module_id": module_id})
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"turn": i, "type": "module", "module": module_id, "error": str(e)})
            continue
        d = r.get("quality", {}).get("completeness", 0)
        comp = r.get("quality", {})
        print(f"D={d:.3f}")
        results.append({
            "turn": i, "type": "module", "module": module_id,
            "D": d, "r": r.get("metrics", {}).get("r", 0),
        })
    else:
        print(f"\n{turn_label}: ✡ Reflect...", end=" ", flush=True)
        try:
            r = post("/reflect", {"mode": "generate"})
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"turn": i, "type": "reflect", "error": str(e)})
            continue
        refl_data = r.get("reflection", {})
        bridge = refl_data.get("bridge", {})
        d_before = refl_data.get("d_before", 0)
        d_after = r.get("quality", {}).get("completeness", refl_data.get("d_after", 0))
        missing = refl_data.get("targeted", [])
        delta_d = refl_data.get("delta_d", 0)
        print(f"D={d_after:.3f} (from {d_before:.3f})")
        if bridge:
            topo = "yes" if bridge.get("topology_available") else "no"
            traj_len = bridge.get("d_trajectory_length", 0)
            floor = bridge.get("floor_rising", "?")
            phase = bridge.get("phase", "?")
            print(f"         Bridge: topo={topo}, traj={traj_len}pts, floor_rising={floor}, phase={phase}")
        results.append({
            "turn": i, "type": "reflect",
            "D_before": d_before, "D_after": d_after,
            "bridge": bridge,
            "missing": missing,
            "delta_d": delta_d,
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
d_values = []
for r in results:
    d = r.get("D") or r.get("D_after") or 0
    d_values.append(d)
    turn = r["turn"]
    ttype = r["type"]
    if "error" in r:
        print(f"  T{turn} [{ttype:8s}]: ERROR - {r['error']}")
    elif ttype == "reflect":
        bridge = r.get("bridge", {})
        bridge_str = ""
        if bridge.get("topology_available"):
            bridge_str += " [TOPO]"
        if bridge.get("d_trajectory_length", 0) > 0:
            bridge_str += f" [TRAJ:{bridge['d_trajectory_length']}]"
        if bridge.get("floor_rising"):
            bridge_str += " [FLOOR↑]"
        print(f"  T{turn} [reflect ]: D={r['D_after']:.3f} (was {r['D_before']:.3f}) missing={r.get('missing',[])} ΔD={r.get('delta_d',0):+.3f}{bridge_str}")
    else:
        print(f"  T{turn} [module  ]: D={d:.3f} [{r.get('module','')}]")

if d_values:
    print(f"\n  Mean D: {sum(d_values)/len(d_values):.3f}")
    print(f"  Max D:  {max(d_values):.3f}")
    print(f"  Min D:  {min(d_values):.3f}")
    d1000 = sum(1 for d in d_values if d >= 0.999)
    print(f"  D=1.000 turns: {d1000}")

# Write raw results
out_path = f"experiments/bridge_session_{session_id[:6] if session_id != 'save_failed' else 'raw'}.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"session_id": session_id, "results": results}, f, indent=2, ensure_ascii=False)
print(f"\n  Raw data: {out_path}")
