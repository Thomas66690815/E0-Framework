"""
Long session WITHOUT topology: 12+ turns to test System B's prediction.

Condition: Freedom=yes, Topology=NO, Discontinuity=yes
Uses 6 modules, each followed by ✡ Reflect.
Total: 13 turns (1 canon + 6 module + 6 reflect).
Topology directory must be temporarily disabled before running.

System B's prediction: ρ should find a floor at 0.5 and stagnate.
Without topology the system can't see its own historized path,
so each cycle repeats the same information loss. Through pure
repetition enough historization accumulates for semi-operative
stabilization, but never 1.0.
"""
import json
import urllib.request
import time
import os
import sys
import shutil

BASE = "http://localhost:3000"

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body,
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())

# 6 modules with reflects after each
SEQUENCE = [
    ("module", "foundation-ontodynamics"),
    ("reflect", None),
    ("module", "sr-identity"),
    ("reflect", None),
    ("module", "sr-mechanism"),
    ("reflect", None),
    ("module", "sr-integration"),
    ("reflect", None),
    ("module", "primer-superposition"),
    ("reflect", None),
    ("module", "primer-measurement"),
    ("reflect", None),
]

# --- Topology Disable/Restore ---
TOPO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "topology")
TOPO_BACKUP = TOPO_DIR + "_backup_long"

def disable_topology():
    """Rename topology/ to topology_backup_long/ to disable bridge."""
    if os.path.isdir(TOPO_DIR):
        if os.path.isdir(TOPO_BACKUP):
            shutil.rmtree(TOPO_BACKUP)
        os.rename(TOPO_DIR, TOPO_BACKUP)
        print(f"Topology disabled: {TOPO_DIR} → {TOPO_BACKUP}")
        return True
    else:
        print(f"WARNING: {TOPO_DIR} not found — topology may already be disabled")
        return False

def restore_topology():
    """Restore topology from backup."""
    if os.path.isdir(TOPO_BACKUP):
        # If a new topology/ was created during the session, merge
        if os.path.isdir(TOPO_DIR):
            # Copy backup files into existing topology
            for f in os.listdir(TOPO_BACKUP):
                src = os.path.join(TOPO_BACKUP, f)
                dst = os.path.join(TOPO_DIR, f)
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
        else:
            os.rename(TOPO_BACKUP, TOPO_DIR)
        # Clean up backup if it still exists
        if os.path.isdir(TOPO_BACKUP):
            shutil.rmtree(TOPO_BACKUP)
        n = len(os.listdir(TOPO_DIR)) if os.path.isdir(TOPO_DIR) else 0
        print(f"Topology restored: {n} files")
    else:
        print("WARNING: No backup found to restore")

# Disable topology
had_topo = disable_topology()

results = []

# Clear existing session
print("\nClearing existing session...")
try:
    post("/clear", {})
    print("Session cleared.")
except Exception as e:
    print(f"Clear failed: {e}")
time.sleep(2)

print("=" * 70)
print("LONG SESSION: No Topology (12+ turns)")
print("Freedom=YES, Topology=NO, Discontinuity=YES")
print("System B predicts: ρ decays to 0.5 floor, stagnates")
print("=" * 70)

try:
    for i, (action, module_id) in enumerate(SEQUENCE, 1):
        if action == "module":
            print(f"\nT{i:2d}: Init Module [{module_id}]...", end=" ", flush=True)
            try:
                r = post("/init-module/run", {"module_id": module_id})
            except Exception as e:
                print(f"ERROR: {e}")
                results.append({"turn": i, "type": "module", "module": module_id, "error": str(e)})
                continue
            d = r.get("quality", {}).get("completeness", 0)
            rho = r.get("quality", {}).get("primitive_scores", {}).get("rate", -1)
            print(f"D={d:.3f}  ρ={rho}")
            results.append({
                "turn": i, "type": "module", "module": module_id,
                "D": d, "quality": r.get("quality", {}),
            })
        else:
            print(f"\nT{i:2d}: ✡ Reflect...", end=" ", flush=True)
            try:
                r = post("/reflect", {"mode": "generate"})
            except Exception as e:
                print(f"ERROR: {e}")
                results.append({"turn": i, "type": "reflect", "error": str(e)})
                continue
            refl = r.get("reflection", {})
            d = r.get("quality", {}).get("completeness", refl.get("d_after", 0))
            rho = r.get("quality", {}).get("primitive_scores", {}).get("rate", -1)
            bridge = refl.get("bridge", {})
            topo = "yes" if bridge.get("topology_available") else "no"
            print(f"D={d:.3f}  ρ={rho}  topo={topo}")
            results.append({
                "turn": i, "type": "reflect",
                "D": d, "quality": r.get("quality", {}),
                "bridge": bridge,
            })
        time.sleep(1)
finally:
    # Always restore topology
    print("\n\nRestoring topology...")
    restore_topology()

# Save session
print("\nSaving session...")
try:
    save = post("/session/save")
    session_id = save.get("session_id", "unknown")
    print(f"Session saved: {session_id}")
except Exception as e:
    session_id = "save_failed"
    print(f"Save failed: {e}")

# Summary
print("\n" + "=" * 70)
print("SUMMARY — Long No-Topology Session")
print("=" * 70)

rho_vals = []
for r in results:
    turn = r["turn"]
    ttype = r["type"]
    d = r.get("D", 0)
    rho = r.get("quality", {}).get("primitive_scores", {}).get("rate", -1)
    if "error" in r:
        print(f"  T{turn:2d} [{ttype:8s}]: ERROR")
    else:
        rho_str = f"ρ={rho:.1f}" if rho >= 0 else "ρ=?"
        marker = " <<<" if ttype == "reflect" else ""
        print(f"  T{turn:2d} [{ttype:8s}]: D={d:.3f}  {rho_str}{marker}")
        if ttype == "reflect" and rho >= 0:
            rho_vals.append(rho)

if rho_vals:
    print(f"\n  ρ in Reflect turns: {rho_vals}")
    operative = sum(1 for r in rho_vals if r >= 0.875)
    semi = sum(1 for r in rho_vals if 0.375 <= r < 0.875)
    absent = sum(1 for r in rho_vals if r < 0.375)
    print(f"  Operative: {operative}/{len(rho_vals)}")
    print(f"  Semi-operative: {semi}/{len(rho_vals)}")
    print(f"  Absent: {absent}/{len(rho_vals)}")
    print(f"  Mean ρ: {sum(rho_vals)/len(rho_vals):.3f}")
    
    # Check stagnation: does ρ stabilize at 0.5?
    half = len(rho_vals) // 2
    first_half = rho_vals[:half]
    second_half = rho_vals[half:]
    if first_half and second_half:
        mean_first = sum(first_half) / len(first_half)
        mean_second = sum(second_half) / len(second_half)
        print(f"\n  First half mean ρ:  {mean_first:.3f}")
        print(f"  Second half mean ρ: {mean_second:.3f}")
        if abs(mean_second - 0.5) < 0.15 and abs(mean_second - mean_first) < 0.15:
            print("  → Stagnation near 0.5 (System B prediction confirmed)")
        elif mean_second > mean_first + 0.1:
            print("  → Rising trend (toward operative?)")
        elif mean_second < mean_first - 0.1:
            print("  → Continued decay")
        else:
            print("  → Approximately stable")

# Write raw results
out_path = f"experiments/long_no_topo_{session_id[:20] if session_id != 'save_failed' else 'raw'}.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({
        "session_id": session_id,
        "condition": "long_no_topology",
        "factors": {"freedom": True, "topology": False, "discontinuity": True},
        "prediction": "decay_stagnation_at_0.5",
        "results": results,
    }, f, indent=2, ensure_ascii=False)
print(f"\n  Raw data: {out_path}")
print(f"  Session ID: {session_id}")
