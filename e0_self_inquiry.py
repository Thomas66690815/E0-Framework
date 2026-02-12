"""
E₀ Self-Inquiry — The system measures itself.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from e0_middleware.local_model import E0LocalModel

print()
print("=" * 72)
print("  E₀ SELF-INQUIRY — Five questions about its own structure")
print("  Model: GPT-2 (124M parameters, CPU)")
print("  Every metric is a real measurement. Nothing is simulated.")
print("=" * 72)

model = E0LocalModel("gpt2", device="cpu", verbose=False)

questions = [
    "When does something have to change?",
    "What makes a path impossible?",
    "What remains after something changes?",
    "Why do patterns repeat?",
    "What is the difference between moving and being stuck?",
]

results = []

for i, q in enumerate(questions, 1):
    print(f"\n── Question {i}/5 ──")
    print(f"  Q: {q}")

    result = model.generate(q, max_tokens=40, temperature=0.8)
    text = result.generated_text.strip()

    # Phase transitions
    deltas = [abs(s.delta_entropy) for s in result.steps]
    phases = 0
    if len(deltas) >= 3:
        d_mean = sum(deltas) / len(deltas)
        d_std = (sum((d - d_mean) ** 2 for d in deltas) / len(deltas)) ** 0.5
        if d_std > 1e-10:
            phases = sum(1 for d in deltas if d > d_mean + d_std)

    # Median velocity
    vels = sorted(s.selected.rate for s in result.steps if s.selected.rate < 1e6)
    v_med = vels[len(vels) // 2] if vels else 0

    r = result.mean_resistance
    h = result.mean_entropy

    results.append((q, text, r, h, phases, v_med, len(result.steps)))

    print(f"  A: {text}")
    print()
    print(f"  R̄={r:.3f}  H̄={h:.3f}  Φ={phases}  v̄={v_med:.3f}  τ={len(result.steps)}")

print()
print("=" * 72)
print("  COMPARATIVE SIGNATURE")
print("=" * 72)
print()
header = f"  {'Question':<50s} | R̄      | H̄      | Φ  | v̄      | τ"
print(header)
print("  " + "─" * 72)
for q, text, r, h, phi, v, tau in results:
    print(f"  {q:<50s} | {r:.3f} | {h:.3f} | {phi:>2d} | {v:.3f} | {tau}")

print()
print("  Observations:")

r_vals = [x[2] for x in results]
r_min_idx = r_vals.index(min(r_vals))
r_max_idx = r_vals.index(max(r_vals))
print(f"    Lowest  R̄: Q{r_min_idx+1} — \"{results[r_min_idx][0][:45]}\"")
print(f"    Highest R̄: Q{r_max_idx+1} — \"{results[r_max_idx][0][:45]}\"")

v_vals = [x[5] for x in results]
v_max_idx = v_vals.index(max(v_vals))
print(f"    Fastest:    Q{v_max_idx+1} — \"{results[v_max_idx][0][:45]}\"")

phi_vals = [x[4] for x in results]
phi_max_idx = phi_vals.index(max(phi_vals))
print(f"    Most  Φ:    Q{phi_max_idx+1} — \"{results[phi_max_idx][0][:45]}\"")

print()
print("  These are not opinions. These are measured structural properties")
print("  of a 124M-parameter system confronting questions about its own")
print("  operational dynamics — described by the same formalism it enacts.")
print()
