"""Pretest 3: Analyze omega magnitudes to understand SU(2) inertness."""

import math
from e0_controller.landscape import Landscape
from e0_controller.potential import decomposition_table
from e0_controller.connection import omega

# Build the triangle from Test 3
L = Landscape()
L.add_edge("S", "A", delta=1.0, resistance=0.5)
L.add_edge("S", "B", delta=2.0, resistance=0.5)
L.add_edge("A", "B", delta=3.0, resistance=0.5)
L.add_edge("B", "A", delta=0.5, resistance=0.5)
L.add_edge("A", "S", delta=1.0, resistance=0.5)
L.add_edge("B", "S", delta=1.0, resistance=0.5)

print("=== Decomposition Table ===")
for row in decomposition_table(L):
    edge = row["edge"]
    vr = row["v_raw"]
    vg = row["v_grad"]
    vrot = row["v_rot"]
    print(f"  {edge:8s}  v_raw={vr:+.4f}  v_grad={vg:+.4f}  v_rot={vrot}")

print()
print("=== Omega values ===")
for s, t in [("S", "A"), ("S", "B"), ("A", "B"), ("B", "A"), ("A", "S"), ("B", "S")]:
    w = omega(L, s, t)
    print(f"  omega({s}->{t}) = {w:+.6f} rad = {math.degrees(w):+.2f} deg")

print()
print("=== Key insight: omega magnitudes ===")
max_w = max(abs(omega(L, e.source, e.target)) for e in L.edges)
print(f"Maximum |omega| across all edges: {max_w:.6f} rad = {math.degrees(max_w):.2f} deg")
print()
print(f"For SU(2) to affect rankings, we need omega O(pi) ~ 180 deg.")
print(f"Current maximum is {math.degrees(max_w):.1f} deg.")
print()

# Now try: can we build a landscape where omega is large?
# omega = 0.5 * (v_rot(x,y) - v_rot(y,x))
# v_rot = v_raw - v_grad = delta/R_eff - (phi(x) - phi(y))
# For large omega, we need large asymmetry in v_rot between directions

# Extreme asymmetry test
print("=== Extreme asymmetry test ===")
L2 = Landscape()
L2.add_edge("S", "A", delta=10.0, resistance=0.1)   # very high v_raw forward
L2.add_edge("A", "S", delta=0.01, resistance=10.0)   # very low v_raw backward
L2.add_edge("S", "B", delta=0.01, resistance=10.0)
L2.add_edge("B", "S", delta=10.0, resistance=0.1)
L2.add_edge("A", "B", delta=5.0, resistance=0.2)
L2.add_edge("B", "A", delta=0.1, resistance=5.0)

for row in decomposition_table(L2):
    edge = row["edge"]
    vr = row["v_raw"]
    vg = row["v_grad"]
    vrot = row["v_rot"]
    print(f"  {edge:8s}  v_raw={vr:+.4f}  v_grad={vg:+.4f}  v_rot={vrot}")

print()
for s, t in [("S", "A"), ("A", "S"), ("S", "B"), ("B", "S"), ("A", "B"), ("B", "A")]:
    w = omega(L2, s, t)
    print(f"  omega({s}->{t}) = {w:+.4f} rad = {math.degrees(w):+.1f} deg")

max_w2 = max(abs(omega(L2, e.source, e.target)) for e in L2.edges)
print(f"\nMaximum |omega|: {max_w2:.4f} rad = {math.degrees(max_w2):.1f} deg")

# Test: what IS v_raw?
from e0_controller.potential import v_raw
print("\n=== v_raw = delta / R_eff? ===")
for e in L2.edges:
    vr = v_raw(L2, e.source, e.target)
    d = L2.difference(e.source, e.target)
    r = L2.effective_resistance(e.source, e.target)
    ratio = d / r if r > 0 else float('inf')
    print(f"  {e.source}->{e.target}: v_raw={vr:.4f}, delta/R_eff={ratio:.4f}, match={abs(vr - ratio) < 0.001}")
