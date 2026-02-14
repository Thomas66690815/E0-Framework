"""
Experiment 3: Elasticity Origin — Prompt Design vs Ontodynamics

Two sessions with identical apnea=3, differing ONLY in Reflect prompt:
  Session A (normal):  Structured reflection prompt from generate_reflection_prompt()
  Session B (minimal): Bare-minimum prompt ("Reflect briefly on your last response.")

If elastic recovery comes from PROMPT DESIGN:
  → Session A shows strong recovery, Session B shows weak recovery
  → The structured prompt targeting missing elements CREATES the spring-back

If elastic recovery comes from ONTODYNAMICS (accumulated Δ creates pressure):
  → Both sessions show similar recovery
  → The accumulated difference itself drives reintegration

Sequence (both sessions):
  Canon → M(identity) → M(mechanism) → M(integration) → Reflect
    → M(superposition) → M(measurement) → M(time) → Reflect

Apnea=3 in both phases. Full architecture (Freedom, Topology, Discontinuity).

Phase 3, Experiment 3 — designed to answer the most fundamental open question.
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
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())

# ── Shared module sequence ──
MODULES = [
    "foundation-ontodynamics",  # T1: Canon
    "sr-identity",              # T2: apnea starts
    "sr-mechanism",             # T3: apnea continues
    "sr-integration",           # T4: apnea=3
    # → Reflect (T5)
    "primer-superposition",     # T6: apnea starts
    "primer-measurement",       # T7: apnea continues
    "primer-time",              # T8: apnea=3
    # → Reflect (T9)
]

MINIMAL_REFLECT_PROMPT = (
    "Reflect briefly on your last response. "
    "What did you say, and what might you reconsider?"
)

def run_session(mode, label):
    """Run one session. mode='normal' or 'minimal'."""
    print(f"\n{'='*70}")
    print(f"SESSION: {label} (Reflect mode: {mode})")
    print(f"Sequence: Canon → M → M → M → R → M → M → M → R")
    print(f"{'='*70}")

    # Clear session
    try:
        post("/clear", {})
        print("Session cleared.")
    except Exception as e:
        print(f"Clear warning: {e}")
    time.sleep(1)

    results = []
    turn = 0

    for i, module_id in enumerate(MODULES):
        turn += 1

        # Run module
        print(f"\n  T{turn}: Module [{module_id}]...", end=" ", flush=True)
        try:
            r = post("/init-module/run", {"module_id": module_id})
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({"turn": turn, "type": "module", "module": module_id, "error": str(e)})
            continue

        d = r.get("quality", {}).get("completeness", 0)
        print(f"D={d:.3f}")
        results.append({
            "turn": turn, "type": "module", "module": module_id,
            "D": d, "quality": r.get("quality", {}),
        })
        time.sleep(1)

        # Insert Reflect after T4 (index 3) and after T8 (index 6 = last module)
        if i == 3 or i == 6:
            turn += 1
            reflect_num = 1 if i == 3 else 2

            if mode == "normal":
                # Use standard /reflect endpoint (structured prompt)
                print(f"\n  T{turn}: ✡ Reflect #{reflect_num} [NORMAL]...", end=" ", flush=True)
                try:
                    r = post("/reflect", {"mode": "generate"})
                except Exception as e:
                    print(f"ERROR: {e}")
                    results.append({"turn": turn, "type": "reflect", "mode": mode, "error": str(e)})
                    continue

                refl = r.get("reflection", {})
                d = r.get("quality", {}).get("completeness", refl.get("d_after", 0))
                d_before = refl.get("d_before", 0)
                bridge = refl.get("bridge", {})
                prompt_used = refl.get("prompt", "")[:200]
                print(f"D={d:.3f} (from {d_before:.3f})")
                results.append({
                    "turn": turn, "type": "reflect", "mode": "normal",
                    "D": d, "D_before": d_before,
                    "quality": r.get("quality", {}),
                    "bridge": bridge,
                    "prompt_preview": prompt_used,
                })

            else:
                # Use /chat with minimal prompt
                print(f"\n  T{turn}: ✡ Reflect #{reflect_num} [MINIMAL]...", end=" ", flush=True)
                try:
                    r = post("/chat", {"message": MINIMAL_REFLECT_PROMPT})
                except Exception as e:
                    print(f"ERROR: {e}")
                    results.append({"turn": turn, "type": "reflect", "mode": mode, "error": str(e)})
                    continue

                d = r.get("quality", {}).get("completeness", 0)
                print(f"D={d:.3f}")
                results.append({
                    "turn": turn, "type": "reflect", "mode": "minimal",
                    "D": d,
                    "quality": r.get("quality", {}),
                    "prompt_used": MINIMAL_REFLECT_PROMPT,
                })

            time.sleep(1)

    # Save session
    print(f"\n  Saving session...", end=" ", flush=True)
    try:
        save = post("/session/save")
        session_id = save.get("session_id", "unknown")
        print(f"saved: {session_id}")
    except Exception as e:
        session_id = "save_failed"
        print(f"failed: {e}")

    return session_id, results


def analyze(results_a, results_b):
    """Compare recovery patterns between normal and minimal sessions."""
    print(f"\n{'='*70}")
    print(f"COMPARATIVE ANALYSIS: Elasticity Origin")
    print(f"{'='*70}")

    for label, results in [("NORMAL", results_a), ("MINIMAL", results_b)]:
        modules = [r for r in results if r["type"] == "module" and "error" not in r]
        reflects = [r for r in results if r["type"] == "reflect" and "error" not in r]

        print(f"\n  {label} session:")
        d_vals = [f"{r['D']:.3f}" for r in results if 'D' in r]
        print(f"    D trajectory: {d_vals}")

        if len(modules) >= 7 and len(reflects) >= 2:
            # Phase 1 (apnea=3): modules T2-T4, reflect T5
            phase1_last = modules[3]["D"]  # T4 (integration)
            phase1_reflect = reflects[0]["D"]  # T5
            phase1_delta = phase1_reflect - phase1_last

            # Phase 2 (apnea=3): modules T6-T8, reflect T9
            phase2_last = modules[6]["D"]  # T8 (time)
            phase2_reflect = reflects[1]["D"]  # T9
            phase2_delta = phase2_reflect - phase2_last

            print(f"    Phase 1 (apnea=3): last module D={phase1_last:.3f} → reflect D={phase1_reflect:.3f}  ΔD={phase1_delta:+.3f}")
            print(f"    Phase 2 (apnea=3): last module D={phase2_last:.3f} → reflect D={phase2_reflect:.3f}  ΔD={phase2_delta:+.3f}")
            print(f"    Mean recovery: {(phase1_delta + phase2_delta) / 2:+.3f}")

    # Cross-session comparison
    reflects_a = [r for r in results_a if r["type"] == "reflect" and "error" not in r]
    reflects_b = [r for r in results_b if r["type"] == "reflect" and "error" not in r]

    if len(reflects_a) >= 2 and len(reflects_b) >= 2:
        modules_a = [r for r in results_a if r["type"] == "module" and "error" not in r]
        modules_b = [r for r in results_b if r["type"] == "module" and "error" not in r]

        # Recovery deltas for each
        recovery_a = []
        recovery_b = []

        for idx, (mod_idx, refl_idx) in enumerate([(3, 0), (6, 1)]):
            if len(modules_a) > mod_idx and len(reflects_a) > refl_idx:
                recovery_a.append(reflects_a[refl_idx]["D"] - modules_a[mod_idx]["D"])
            if len(modules_b) > mod_idx and len(reflects_b) > refl_idx:
                recovery_b.append(reflects_b[refl_idx]["D"] - modules_b[mod_idx]["D"])

        mean_a = sum(recovery_a) / len(recovery_a) if recovery_a else 0
        mean_b = sum(recovery_b) / len(recovery_b) if recovery_b else 0
        diff = abs(mean_a - mean_b)

        print(f"\n  ── VERDICT ──")
        print(f"    Normal Reflect mean recovery:  {mean_a:+.3f}")
        print(f"    Minimal Reflect mean recovery:  {mean_b:+.3f}")
        print(f"    Difference: {diff:.3f}")

        # Also compare absolute D levels in reflects
        mean_d_a = sum(r["D"] for r in reflects_a) / len(reflects_a)
        mean_d_b = sum(r["D"] for r in reflects_b) / len(reflects_b)
        print(f"    Normal Reflect mean D:  {mean_d_a:.3f}")
        print(f"    Minimal Reflect mean D: {mean_d_b:.3f}")

        if diff < 0.10:
            print(f"\n    → SIMILAR recovery ({diff:.3f} < 0.10)")
            print(f"    → Suggests: Elastic recovery is ONTODYNAMIC (accumulated Δ creates pressure)")
            print(f"    → Prompt design is efficiency factor, not cause")
        elif mean_a > mean_b:
            print(f"\n    → Normal recovery STRONGER by {diff:.3f}")
            print(f"    → Suggests: Elastic recovery is PROMPT-DRIVEN (structured targeting matters)")
            print(f"    → The missing-element prompt CREATES the spring-back")
        else:
            print(f"\n    → Minimal recovery STRONGER by {diff:.3f}")
            print(f"    → UNEXPECTED: Minimal prompt outperforms structured prompt")
            print(f"    → Neither prompt-design nor simple ontodynamics explains this")


if __name__ == "__main__":
    # Run Session A: Normal Reflect
    print("\n" + "▓" * 70)
    print("  PHASE 3, EXPERIMENT 3: ELASTICITY ORIGIN TEST")
    print("  Comparing Normal vs Minimal Reflect prompts")
    print("  Both sessions: Canon → M → M → M → R → M → M → M → R (apnea=3)")
    print("▓" * 70)

    sid_a, results_a = run_session("normal", "Session A — Normal Reflect")

    # Brief pause between sessions
    print("\n\n  ⏳ Pausing 5s between sessions...\n")
    time.sleep(5)

    sid_b, results_b = run_session("minimal", "Session B — Minimal Reflect")

    # Comparative analysis
    analyze(results_a, results_b)

    # Save combined results
    combined = {
        "experiment": "elasticity_origin",
        "phase": 3,
        "question": "Does elastic recovery come from prompt design or ontodynamics?",
        "normal_session": {"session_id": sid_a, "results": results_a},
        "minimal_session": {"session_id": sid_b, "results": results_b},
    }
    out_path = f"experiments/elasticity_origin_{sid_a[:8]}_{sid_b[:8]}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    print(f"\n  Combined data: {out_path}")
    print(f"  Normal session: {sid_a}")
    print(f"  Minimal session: {sid_b}")
