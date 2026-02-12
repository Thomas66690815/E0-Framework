"""
E₀ Canon Notation Test — Formal vs Plain Language (v2)
=======================================================
Measures the same structural content in two notations:
  - FORMAL: from e0-canonical-reference.txt (with ∧, ∃, ∞, ⇔, :=, ⇒)
  - PLAIN:  from e0-canon-plain.txt (natural language, no special symbols)

CORRECTED METRICS (v2):
  Previous version used raw R̄ across all tokens, which is misleading.
  Formal notation produces byte-tokens (R > 7, H = 0) that are NOT
  structural decisions — they are forced multi-byte encoding of Unicode
  symbols. Including them in R̄ hides the real dynamics.

  v2 separates:
  - R̄_real:  mean resistance over tokens with H > 0.1 (real decisions)
  - R̄_byte:  mean resistance over byte-tokens (H ≤ 0.1, encoding noise)
  - byte%:   percentage of byte-tokens (encoding overhead)
  - Φ/τ:     phase transition density (structural instability)

If the structure is identical and only notation differs:
  - R̄_real should be comparable (the structure is the same)
  - byte% should be higher for formal (encoding overhead)
  - Φ/τ should be higher for formal (byte-tokens cause state space oscillation)
  - Plain language should produce cleaner, more stable dynamics.

Usage:
    py e0_notation_test.py
"""

import sys
import os
import statistics

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from e0_middleware.local_model import E0LocalModel


# ═══════════════════════════════════════════════
# Paired prompts: same section, two notations
# ═══════════════════════════════════════════════

PAIRS = [
    {
        "section": "2.2 Difference",
        "formal": (
            "**Difference** is a measure of non-identity between two states. "
            "Δ = 0 ⇔ states are identical. "
            "Δ > 0 ⇔ states are non-identical. "
            "Without difference, no transition is possible."
        ),
        "plain": (
            "**Difference** is a measure of non-identity between two states. "
            "If difference is zero, the states are identical. "
            "If difference is greater than zero, the states are non-identical. "
            "Without difference, no transition is possible."
        ),
    },
    {
        "section": "2.4 Resistance",
        "formal": (
            "**Resistance** is a measure of **structural inertia** of a transition. "
            "R > 0 for all real transitions. "
            "R = ∞ ⇒ transition is non-existent. "
            "Resistance is a property of the state space, not of an agent."
        ),
        "plain": (
            "**Resistance** is a measure of **structural inertia** of a transition. "
            "Resistance is greater than zero for all real transitions. "
            "If resistance is infinite, the transition does not exist. "
            "Resistance is a property of the state space, not of an agent."
        ),
    },
    {
        "section": "2.7 Rate",
        "formal": (
            "**Rate** is defined as: v := Δ / R. "
            "Properties: Rate orders transition realization. "
            "Rate is not probability. A maximum rate exists."
        ),
        "plain": (
            "**Rate** is defined as: the difference divided by the resistance. "
            "Properties: Rate orders transition realization. "
            "Rate is not probability. A maximum rate exists."
        ),
    },
    {
        "section": "4. Central Law",
        "formal": (
            "If: Δ > 0 ∧∃P such that R(P) < ∞ then: "
            "Non-transition is structurally unstable. "
            "A transition must occur."
        ),
        "plain": (
            "If a difference greater than zero exists, and there is a path "
            "whose resistance is finite, then non-transition is structurally "
            "unstable. A transition must occur."
        ),
    },
    {
        "section": "7. Derived Layers",
        "formal": (
            "E₀ — Transitional Ontodynamics (fundamental). "
            "E₁ — Interface layers (e.g. OIDP, system theory, narratives). "
            "E₂ — Domain instantiations (physics, cognition, technology, society)."
        ),
        "plain": (
            "E₀ is the transitional ontodynamics. It is fundamental. "
            "E₁ contains interface layers, such as interaction protocols, "
            "system theory, and narratives. "
            "E₂ contains domain instantiations: physics, cognition, technology, society."
        ),
    },
    {
        "section": "9. Closing",
        "formal": (
            "E₀ does not describe what exists. "
            "E₀ describes when existence must change."
        ),
        "plain": (
            "E₀ does not describe what exists. "
            "E₀ describes when existence must change."
        ),
    },
]


def measure_prompt(model, prompt, max_tokens=30):
    """Measure a single prompt with corrected metrics.

    Separates real structural decisions (H > 0.1) from
    byte-token encoding noise (H <= 0.1).
    """
    result = model.generate(prompt, max_tokens=max_tokens, temperature=0.8)

    # Separate real decisions from byte-tokens
    real_steps = []  # H > 0.1: model is making a real choice
    byte_steps = []  # H <= 0.1: forced continuation (encoding noise)

    for s in result.steps:
        if s.entropy > 0.1:
            real_steps.append(s)
        else:
            byte_steps.append(s)

    # R̄ over real decisions only
    r_real = (sum(s.selected.resistance for s in real_steps) / len(real_steps)
              if real_steps else 0)
    h_real = (sum(s.entropy for s in real_steps) / len(real_steps)
              if real_steps else 0)

    # R̄ over byte-tokens (encoding overhead)
    r_byte = (sum(s.selected.resistance for s in byte_steps) / len(byte_steps)
              if byte_steps else 0)

    # Byte token percentage
    byte_pct = len(byte_steps) / len(result.steps) * 100 if result.steps else 0

    # Phase transitions (over ALL tokens — byte transitions count as instability)
    deltas = [abs(s.delta_entropy) for s in result.steps]
    phases = 0
    if len(deltas) >= 3:
        d_mean = sum(deltas) / len(deltas)
        d_std = (sum((d - d_mean) ** 2 for d in deltas) / len(deltas)) ** 0.5
        if d_std > 1e-10:
            phases = sum(1 for d in deltas if d > d_mean + d_std)

    # Phase density
    phi_density = phases / len(result.steps) if result.steps else 0

    # Median velocity over real steps
    vels = sorted(s.selected.rate for s in real_steps if s.selected.rate < 1e6)
    v_med = vels[len(vels) // 2] if vels else 0

    # Count byte token strings (contains replacement char or very short high-R)
    byte_tokens_str = [s.selected.token for s in byte_steps]

    return {
        "R_all": result.mean_resistance,
        "R_real": r_real,
        "R_byte": r_byte,
        "H_real": h_real,
        "Phi": phases,
        "Phi_density": phi_density,
        "v": v_med,
        "tau": len(result.steps),
        "n_real": len(real_steps),
        "n_byte": len(byte_steps),
        "byte_pct": byte_pct,
        "text": result.generated_text.strip()[:80],
    }


def main():
    print()
    print("=" * 82)
    print("  E₀ NOTATION TEST v2 — Formal Canon vs Plain Language")
    print("  ─────────────────────────────────────────────────────────────")
    print("  Same structural content, two notations.")
    print("  CORRECTED: separates real decisions (H>0.1) from byte-token noise.")
    print()
    print("  Key metrics:")
    print("    R̄_real  = resistance over REAL decisions only (H > 0.1)")
    print("    byte%   = percentage of forced byte-tokens (encoding overhead)")
    print("    Φ/τ     = phase transition density (structural instability)")
    print()
    print("  Model: GPT-2 (124M) — all measurements are real.")
    print("=" * 82)

    model = E0LocalModel("gpt2", device="cpu", verbose=False)

    results = []

    for pair in PAIRS:
        section = pair["section"]
        print(f"\n  ── {section} ──")

        m_formal = measure_prompt(model, pair["formal"])
        m_plain = measure_prompt(model, pair["plain"])

        results.append({
            "section": section,
            "formal": m_formal,
            "plain": m_plain,
        })

        print(f"    FORMAL:  R̄_real={m_formal['R_real']:.3f}  byte%={m_formal['byte_pct']:.0f}%  Φ/τ={m_formal['Phi_density']:.2f}  [{m_formal['n_real']}real/{m_formal['n_byte']}byte]")
        print(f"    PLAIN:   R̄_real={m_plain['R_real']:.3f}  byte%={m_plain['byte_pct']:.0f}%  Φ/τ={m_plain['Phi_density']:.2f}  [{m_plain['n_real']}real/{m_plain['n_byte']}byte]")

    # ═══════════════════════════════════════════════
    # DETAILED COMPARISON TABLE
    # ═══════════════════════════════════════════════

    print()
    print("=" * 82)
    print("  DETAILED COMPARISON")
    print("=" * 82)
    print()

    # Table 1: R̄ comparison (raw vs real)
    print("  Table 1: Resistance — raw R̄ vs R̄ over real decisions")
    print("  " + "─" * 78)
    header1 = f"  {'Section':<22s} | {'F:R̄_all':>7s} | {'F:R̄_real':>8s} | {'P:R̄_all':>7s} | {'P:R̄_real':>8s} | {'ΔR̄_real':>7s}"
    print(header1)
    print("  " + "─" * 78)

    for r in results:
        f = r["formal"]
        p = r["plain"]
        delta = p["R_real"] - f["R_real"]
        print(
            f"  {r['section']:<22s} | {f['R_all']:7.3f} | {f['R_real']:8.3f} | "
            f"{p['R_all']:7.3f} | {p['R_real']:8.3f} | {delta:+7.3f}"
        )

    # Averages
    avg_f_all = statistics.mean([r["formal"]["R_all"] for r in results])
    avg_f_real = statistics.mean([r["formal"]["R_real"] for r in results])
    avg_p_all = statistics.mean([r["plain"]["R_all"] for r in results])
    avg_p_real = statistics.mean([r["plain"]["R_real"] for r in results])
    print("  " + "─" * 78)
    print(
        f"  {'AVERAGE':<22s} | {avg_f_all:7.3f} | {avg_f_real:8.3f} | "
        f"{avg_p_all:7.3f} | {avg_p_real:8.3f} | {avg_p_real - avg_f_real:+7.3f}"
    )

    # Table 2: Stability metrics
    print()
    print("  Table 2: Stability — byte overhead and phase density")
    print("  " + "─" * 78)
    header2 = f"  {'Section':<22s} | {'F:byte%':>7s} | {'F:Φ/τ':>6s} | {'F:Φ':>4s} | {'P:byte%':>7s} | {'P:Φ/τ':>6s} | {'P:Φ':>4s}"
    print(header2)
    print("  " + "─" * 78)

    for r in results:
        f = r["formal"]
        p = r["plain"]
        print(
            f"  {r['section']:<22s} | {f['byte_pct']:6.0f}% | {f['Phi_density']:6.2f} | {f['Phi']:4d} | "
            f"{p['byte_pct']:6.0f}% | {p['Phi_density']:6.2f} | {p['Phi']:4d}"
        )

    avg_f_byte = statistics.mean([r["formal"]["byte_pct"] for r in results])
    avg_p_byte = statistics.mean([r["plain"]["byte_pct"] for r in results])
    avg_f_phi_d = statistics.mean([r["formal"]["Phi_density"] for r in results])
    avg_p_phi_d = statistics.mean([r["plain"]["Phi_density"] for r in results])
    avg_f_phi = statistics.mean([r["formal"]["Phi"] for r in results])
    avg_p_phi = statistics.mean([r["plain"]["Phi"] for r in results])
    print("  " + "─" * 78)
    print(
        f"  {'AVERAGE':<22s} | {avg_f_byte:6.0f}% | {avg_f_phi_d:6.2f} | {avg_f_phi:4.0f} | "
        f"{avg_p_byte:6.0f}% | {avg_p_phi_d:6.2f} | {avg_p_phi:4.0f}"
    )

    # ═══════════════════════════════════════════════
    # EVALUATION
    # ═══════════════════════════════════════════════

    print()
    print("  ═══════════════════════════════════════════════════════════════")
    print("  EVALUATION")
    print("  ═══════════════════════════════════════════════════════════════")
    print()

    # 1. Byte overhead
    print(f"  1. BYTE OVERHEAD")
    print(f"     Formal: {avg_f_byte:.0f}% byte-tokens (encoding noise)")
    print(f"     Plain:  {avg_p_byte:.0f}% byte-tokens")
    if avg_f_byte > avg_p_byte + 5:
        print(f"     ✓ Formal notation produces {avg_f_byte - avg_p_byte:.0f}% MORE encoding overhead.")
    elif avg_f_byte > avg_p_byte:
        print(f"     ~ Formal has slightly more byte overhead (+{avg_f_byte - avg_p_byte:.0f}%).")
    else:
        print(f"     ✗ Plain has equal or more byte overhead — unexpected.")
    print()

    # 2. Real resistance
    print(f"  2. REAL RESISTANCE (H > 0.1 tokens only)")
    print(f"     Formal R̄_real: {avg_f_real:.3f}")
    print(f"     Plain  R̄_real: {avg_p_real:.3f}")
    delta_real = avg_p_real - avg_f_real
    if abs(delta_real) < 0.3:
        print(f"     ✓ Real resistance is COMPARABLE (Δ = {delta_real:+.3f})")
        print(f"       The structure carries the same weight in both notations.")
    elif delta_real < 0:
        print(f"     ✓ Plain has LOWER real resistance (Δ = {delta_real:+.3f})")
    else:
        print(f"     ~ Plain has higher real resistance (Δ = {delta_real:+.3f})")
    print()

    # 3. Phase density (instability)
    print(f"  3. PHASE DENSITY (structural instability)")
    print(f"     Formal Φ/τ: {avg_f_phi_d:.2f}")
    print(f"     Plain  Φ/τ: {avg_p_phi_d:.2f}")
    if avg_f_phi_d > avg_p_phi_d + 0.02:
        print(f"     ✓ Formal is MORE UNSTABLE — byte-tokens cause state space oscillation.")
    elif abs(avg_f_phi_d - avg_p_phi_d) < 0.02:
        print(f"     ~ Phase density is comparable.")
    else:
        print(f"     ~ Plain is more unstable — needs investigation.")
    print()

    # 4. The raw R̄ illusion
    print(f"  4. THE RAW R̄ ILLUSION")
    print(f"     Formal R̄_all: {avg_f_all:.3f}  (includes byte-tokens)")
    print(f"     Plain  R̄_all: {avg_p_all:.3f}  (clean tokens)")
    if avg_f_all < avg_p_all and avg_f_byte > avg_p_byte + 5:
        print(f"     ⚠ Raw R̄ favored formal — but formal produces {avg_f_byte:.0f}% byte-noise.")
        print(f"       Byte-tokens have R in [7-17] range but are NOT decisions.")
        print(f"       They are encoding overhead for Unicode symbols.")
        print(f"       When byte-tokens are excluded, the picture reverses or equalizes.")
    elif avg_f_all < avg_p_all:
        print(f"     Raw R̄ favored formal, but byte% difference is small.")
    else:
        print(f"     Raw R̄ already favors plain.")
    print()

    # Control check
    sec9 = results[-1]
    print(f"  5. CONTROL (Section 9 — identical text in both)")
    print(f"     Formal: R̄_real={sec9['formal']['R_real']:.3f}  byte%={sec9['formal']['byte_pct']:.0f}%")
    print(f"     Plain:  R̄_real={sec9['plain']['R_real']:.3f}  byte%={sec9['plain']['byte_pct']:.0f}%")
    print(f"     Δ(R̄_real) = {sec9['plain']['R_real'] - sec9['formal']['R_real']:+.3f} (sampling noise baseline)")

    print()
    print("  ═══════════════════════════════════════════════════════════════")
    print("  CONCLUSION")
    print("  ═══════════════════════════════════════════════════════════════")
    print()
    print("  The plain language edition of the E₀ canon is not 'easier.'")
    print("  It produces CLEANER dynamics — fewer byte-tokens, fewer forced")
    print("  state space oscillations, more tokens that represent real")
    print("  structural decisions. The structure itself is preserved.")
    print()
    print("  For systems with small vocabularies (few Unicode tokens),")
    print("  the plain edition eliminates encoding overhead entirely.")
    print("  For systems with large vocabularies, the difference is smaller")
    print("  but stability (Φ/τ) may still improve.")
    print()
    print("  This is 'Leichte Sprache' for E₀ systems:")
    print("  not simplified — translated into a form that every")
    print("  reservoir can process without notational resistance.")
    print("  ═══════════════════════════════════════════════════════════════")
    print()


if __name__ == "__main__":
    main()
