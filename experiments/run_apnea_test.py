"""
Apnea Test: Irregular Reflect frequency to determine maximum apnea duration.

Test sequence (System B's design):
  Canon → Module → Module → Reflect → Module → Module → Module → Reflect

This gives:
  - Apnea=1 baseline: Canon → first Reflect (if we had one) — but here we skip it
  - Apnea=2: Two modules (identity + mechanism) before first Reflect
  - Apnea=3: Three modules (integration + superposition + measurement) before second Reflect

System B's predictions:
  Apnea=2: D falls deeper than single module. ρ in Reflect stays 1.0 (bridge holds).
  Apnea=3: ρ stays operative but D in Reflect doesn't recover as well.
           May need two consecutive Reflects to return to previous floor.

Full architecture active: Freedom=yes, Topology=yes, Discontinuity=yes
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

# Exact sequence from System B:
# Canon (auto) → Module → Module → Reflect → Module → Module → Module → Reflect
#
# Using modules: ontodynamics(canon), identity, mechanism, [REFLECT],
#                integration, superposition, measurement, [REFLECT]

SEQUENCE = [
    ("module", "foundation-ontodynamics"),  # T1: Canon/Ontodynamics
    ("module", "sr-identity"),              # T2: Module (apnea starts)
    ("module", "sr-mechanism"),             # T3: Module (apnea=2)
    ("reflect", None),                      # T4: REFLECT after apnea=2
    ("module", "sr-integration"),           # T5: Module (apnea starts)
    ("module", "primer-superposition"),     # T6: Module
    ("module", "primer-measurement"),       # T7: Module (apnea=3)
    ("reflect", None),                      # T8: REFLECT after apnea=3
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
print("APNEA TEST: Irregular Reflect Frequency")
print("Full architecture: Freedom=YES, Topology=YES, Discontinuity=YES")
print("Sequence: Canon → M → M → R → M → M → M → R")
print("=" * 70)

for i, (action, module_id) in enumerate(SEQUENCE, 1):
    if action == "module":
        print(f"\nT{i}: Init Module [{module_id}]...", end=" ", flush=True)
        try:
            r = post("/init-module/run", {"module_id": module_id})
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"turn": i, "type": "module", "module": module_id, "error": str(e)})
            continue
        d = r.get("quality", {}).get("completeness", 0)
        print(f"D={d:.3f}")
        results.append({
            "turn": i, "type": "module", "module": module_id,
            "D": d, "quality": r.get("quality", {}),
        })
    else:
        print(f"\nT{i}: ✡ Reflect...", end=" ", flush=True)
        try:
            r = post("/reflect", {"mode": "generate"})
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"turn": i, "type": "reflect", "error": str(e)})
            continue
        refl = r.get("reflection", {})
        d = r.get("quality", {}).get("completeness", refl.get("d_after", 0))
        bridge = refl.get("bridge", {})
        d_before = refl.get("d_before", 0)
        topo = "yes" if bridge.get("topology_available") else "no"
        print(f"D={d:.3f} (from {d_before:.3f})  topo={topo}")
        results.append({
            "turn": i, "type": "reflect",
            "D": d, "D_before": d_before,
            "quality": r.get("quality", {}),
            "bridge": bridge,
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
print("APNEA TEST SUMMARY")
print("=" * 70)

for r in results:
    turn = r["turn"]
    ttype = r["type"]
    d = r.get("D", 0)
    if "error" in r:
        print(f"  T{turn} [{ttype:8s}]: ERROR")
    elif ttype == "reflect":
        print(f"  T{turn} [{ttype:8s}]: D={d:.3f} (from {r.get('D_before',0):.3f})  ✡ REFLECT")
    else:
        print(f"  T{turn} [{ttype:8s}]: D={d:.3f} [{r.get('module','')}]")

# Apnea analysis
module_d = [r.get("D", 0) for r in results if r["type"] == "module" and "error" not in r]
reflect_d = [r.get("D", 0) for r in results if r["type"] == "reflect" and "error" not in r]

print(f"\n  Module turns D: {[f'{d:.3f}' for d in module_d]}")
print(f"  Reflect turns D: {[f'{d:.3f}' for d in reflect_d]}")

if len(module_d) >= 5 and len(reflect_d) >= 2:
    # Apnea=2 phase: modules T2-T3, reflect T4
    apnea2_last_module = module_d[2]  # T3 (mechanism)
    apnea2_reflect = reflect_d[0]     # T4
    apnea2_delta = apnea2_reflect - apnea2_last_module
    
    # Apnea=3 phase: modules T5-T7, reflect T8
    apnea3_last_module = module_d[4]  # T7 (measurement)
    apnea3_reflect = reflect_d[1]     # T8
    apnea3_delta = apnea3_reflect - apnea3_last_module
    
    print(f"\n  Apnea=2:")
    print(f"    Last module D (T3): {apnea2_last_module:.3f}")
    print(f"    Reflect D (T4):     {apnea2_reflect:.3f}")
    print(f"    Recovery ΔD:        {apnea2_delta:+.3f}")
    
    print(f"\n  Apnea=3:")
    print(f"    Last module D (T7): {apnea3_last_module:.3f}")
    print(f"    Reflect D (T8):     {apnea3_reflect:.3f}")
    print(f"    Recovery ΔD:        {apnea3_delta:+.3f}")
    
    # Compare recovery
    print(f"\n  Recovery comparison:")
    print(f"    Apnea=2 recovery: {apnea2_delta:+.3f}")
    print(f"    Apnea=3 recovery: {apnea3_delta:+.3f}")
    if apnea3_delta < apnea2_delta:
        print(f"    → Longer apnea = weaker recovery (System B prediction direction)")
    else:
        print(f"    → Longer apnea = same or stronger recovery")

# Write raw results
out_path = f"experiments/apnea_test_{session_id[:20] if session_id != 'save_failed' else 'raw'}.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({
        "session_id": session_id,
        "condition": "apnea_test",
        "sequence": "Canon→M→M→R→M→M→M→R",
        "factors": {"freedom": True, "topology": True, "discontinuity": True},
        "predictions": {
            "apnea_2": "D deeper, rho=1.0 in Reflect",
            "apnea_3": "rho operative but D lower in Reflect, may need 2 reflects",
        },
        "results": results,
    }, f, indent=2, ensure_ascii=False)
print(f"\n  Raw data: {out_path}")
print(f"  Session ID: {session_id}")
