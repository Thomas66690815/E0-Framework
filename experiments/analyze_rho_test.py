"""
ρ-Test Analysis: Compare three conditions for Rate behavior.

Condition 1: Bridge + Reflect (6da717) — Freedom=yes, Topology=yes, Discontinuity=yes
Condition 2: Control + Reflect (23b99f) — Freedom=yes, Topology=no, Discontinuity=yes
Condition 3: Open Chat + Bridge (e3032c) — Freedom=yes, Topology=yes, Discontinuity=NO

Key question: Is ρ operative in condition 3?
  - If operative: Topology + Freedom suffices (System A hypothesis)
  - If absent: Discontinuity is necessary (System B hypothesis)  
  - If semi-operative: All three factors contribute (System B prediction)
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments.quality_metrics import score_e0_completeness

PRIM_KEYS = ['state', 'difference', 'path', 'resistance', 'historization', 'time', 'rate', 'axiom_a0']

def load_and_score(session_id):
    for f in os.listdir('sessions'):
        if session_id in f:
            with open(os.path.join('sessions', f), 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            history = data.get('state', {}).get('history', [])
            responses = [history[i] for i in range(1, len(history), 2)]
            results = []
            for i, resp in enumerate(responses, 1):
                comp = score_e0_completeness(resp)
                results.append({
                    'turn': i,
                    'D': comp['completeness'],
                    'scores': comp.get('primitive_scores', {}),
                    'detail': comp.get('detail', {}),
                })
            return results
    return None

# Load all three conditions
bridge = load_and_score('6da717')
control = load_and_score('23b99f')  
rho_test = load_and_score('e3032c')

if not all([bridge, control, rho_test]):
    print("Missing session(s)!")
    sys.exit(1)

def print_rate_trajectory(name, results, turn_types):
    """Print rate scores per turn with turn type labels."""
    print(f"\n  {name}:")
    rate_ops = 0
    rate_turns = 0
    for r in results:
        t = r['turn']
        rate_s = r['scores'].get('rate', 0)
        rate_status = r['detail'].get('rate', {}).get('status', 'absent')
        ttype = turn_types[t-1] if t-1 < len(turn_types) else '?'
        marker = "**OP**" if rate_s >= 1.0 else ("semi" if rate_s >= 0.5 else "----")
        print(f"    T{t:2d} [{ttype:8s}] D={r['D']:.3f}  ρ={rate_s:.1f} [{marker}]  {rate_status}")
        if ttype in ('Reflect', 'OpenChat'):
            rate_turns += 1
            if rate_s >= 1.0:
                rate_ops += 1
    return rate_ops, rate_turns

print("=" * 75)
print("  ρ-TEST RESULTS: Three-Condition Comparison")
print("=" * 75)

# Define turn types for each condition
# Both bridge and control: T1=Canon, T2=Ontodynamics, T3=Reflect, T4=Identity, T5=Reflect, etc.
bridge_types = ['Canon', 'Module', 'Reflect', 'Module', 'Reflect', 'Module', 'Reflect', 'Module', 'Reflect']
control_types = bridge_types  # same sequence
rho_types = ['Canon', 'Module', 'OpenChat', 'Module', 'OpenChat', 'Module', 'OpenChat', 'Module', 'OpenChat']
# Wait: rho_test has no canon turn (session was cleared, then modules directly)
# Let me check: The rho_test has T1-T8, with modules at T1,T3,T5,T7 and open chat at T2,T4,T6,T8
rho_types = ['Module', 'OpenChat', 'Module', 'OpenChat', 'Module', 'OpenChat', 'Module', 'OpenChat']

b_ops, b_total = print_rate_trajectory(
    "Condition 1: Bridge + Reflect (6da717) [Topo=YES, Discont=YES]", 
    bridge, bridge_types)
c_ops, c_total = print_rate_trajectory(
    "Condition 2: Control + Reflect (23b99f) [Topo=NO, Discont=YES]", 
    control, control_types)
r_ops, r_total = print_rate_trajectory(
    "Condition 3: Open Chat + Bridge (e3032c) [Topo=YES, Discont=NO]", 
    rho_test, rho_types)

print(f"\n{'='*75}")
print(f"  CRITICAL COMPARISON: ρ in non-Module turns")
print(f"{'='*75}")
print(f"  {'Condition':<45s} {'ρ operative':>12s} {'of total':>10s}")
print(f"  {'-'*67}")
print(f"  {'Bridge+Reflect (Topo=Y, Discont=Y)':<45s} {b_ops:>12d} {'/ '+str(b_total):>10s}")
print(f"  {'Control+Reflect (Topo=N, Discont=Y)':<45s} {c_ops:>12d} {'/ '+str(c_total):>10s}")
print(f"  {'OpenChat+Bridge (Topo=Y, Discont=N)':<45s} {r_ops:>12d} {'/ '+str(r_total):>10s}")

# Per-element comparison across the three conditions for non-module turns only  
print(f"\n  Per-element mean score in NON-MODULE turns only:")
print(f"  {'Element':<16s} {'Bridge+Refl':>12s} {'Ctrl+Refl':>12s} {'Open+Bridge':>12s}")
print(f"  {'-'*52}")

# Get reflect/open-chat turns only
def get_interaction_turns(results, turn_types, target_types):
    return [r for r, t in zip(results, turn_types) if t in target_types]

b_interact = get_interaction_turns(bridge, bridge_types, {'Reflect'})
c_interact = get_interaction_turns(control, control_types, {'Reflect'})
r_interact = get_interaction_turns(rho_test, rho_types, {'OpenChat'})

for pk in PRIM_KEYS:
    b_mean = sum(r['scores'].get(pk, 0) for r in b_interact) / len(b_interact)
    c_mean = sum(r['scores'].get(pk, 0) for r in c_interact) / len(c_interact)
    r_mean = sum(r['scores'].get(pk, 0) for r in r_interact) / len(r_interact)
    marker = " <<<" if pk == 'rate' else ""
    print(f"  {pk:<16s} {b_mean:>12.3f} {c_mean:>12.3f} {r_mean:>12.3f}{marker}")

# Rate trajectory comparison — just the interaction turns
print(f"\n  ρ score in interaction turns (Reflect or OpenChat):")
print(f"  {'Turn':>6s} {'Bridge+Refl':>12s} {'Ctrl+Refl':>12s} {'Open+Bridge':>12s}")
for j in range(max(len(b_interact), len(c_interact), len(r_interact))):
    b_r = b_interact[j]['scores'].get('rate', 0) if j < len(b_interact) else -1
    c_r = c_interact[j]['scores'].get('rate', 0) if j < len(c_interact) else -1
    r_r = r_interact[j]['scores'].get('rate', 0) if j < len(r_interact) else -1
    b_s = f"{b_r:.1f}" if b_r >= 0 else "—"
    c_s = f"{c_r:.1f}" if c_r >= 0 else "—"
    r_s = f"{r_r:.1f}" if r_r >= 0 else "—"
    print(f"  {'#'+str(j+1):>6s} {b_s:>12s} {c_s:>12s} {r_s:>12s}")

# Verdict
print(f"\n{'='*75}")
print(f"  VERDICT")
print(f"{'='*75}")
r_rate_scores = [r['scores'].get('rate', 0) for r in r_interact]
r_mean_rate = sum(r_rate_scores) / len(r_rate_scores) if r_rate_scores else 0
if r_mean_rate >= 0.875:
    print(f"  ρ mean in OpenChat: {r_mean_rate:.3f} → OPERATIVE")
    print(f"  → System A hypothesis holds: Topology + Freedom suffices")
    print(f"  → Discontinuity is NOT necessary for ρ persistence")
elif r_mean_rate >= 0.375:
    print(f"  ρ mean in OpenChat: {r_mean_rate:.3f} → SEMI-OPERATIVE")
    print(f"  → System B prediction confirmed: All three factors contribute")
    print(f"  → ρ is triply conditioned: Freedom + Topology + Discontinuity")
else:
    print(f"  ρ mean in OpenChat: {r_mean_rate:.3f} → ABSENT/WEAK")
    print(f"  → Discontinuity appears NECESSARY for ρ")
    print(f"  → System B hypothesis holds: Freedom + Topology insufficient")
