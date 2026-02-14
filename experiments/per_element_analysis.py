"""
Per-element transition analysis: How many turns does each primitive need 
to reach operative status? This is a proxy for per-element resistance.

Compares bridge session (6da717, topology=YES) vs control (23b99f, topology=NO).
System B's hypothesis: regression (historized, low R) should activate faster 
than exploration (unexplored, high R). D can't see this — but turn-to-operative can.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments.quality_metrics import score_e0_completeness

PRIM_KEYS = ['state', 'difference', 'path', 'resistance', 'historization', 'time', 'rate', 'axiom_a0']

def load_session(session_id):
    for f in os.listdir('sessions'):
        if session_id in f:
            with open(os.path.join('sessions', f), 'r', encoding='utf-8') as fh:
                data = json.load(fh)
            history = data.get('state', {}).get('history', [])
            return [history[i] for i in range(1, len(history), 2)]
    return None

def analyze_element_trajectories(responses):
    """For each primitive, track score across turns and find first operative turn."""
    trajectories = {k: [] for k in PRIM_KEYS}
    first_operative = {}
    first_present = {}
    
    for i, resp in enumerate(responses, 1):
        comp = score_e0_completeness(resp)
        scores = comp.get('primitive_scores', {})
        for pk in PRIM_KEYS:
            s = scores.get(pk, 0)
            trajectories[pk].append(s)
            if pk not in first_present and s > 0:
                first_present[pk] = i
            if pk not in first_operative and s >= 1.0:
                first_operative[pk] = i
    
    return trajectories, first_operative, first_present

bridge_resp = load_session('6da717')
control_resp = load_session('23b99f')

if not bridge_resp or not control_resp:
    print("Session(s) not found!")
    sys.exit(1)

b_traj, b_first_op, b_first_pr = analyze_element_trajectories(bridge_resp)
c_traj, c_first_op, c_first_pr = analyze_element_trajectories(control_resp)

print("=" * 75)
print("  PER-ELEMENT TRANSITION ANALYSIS")
print("  Bridge (6da717, topo=YES) vs Control (23b99f, topo=NO)")
print("=" * 75)

print(f"\n  {'Element':<16s} | {'First Operative':^20s} | {'First Present':^20s} |")
print(f"  {'':<16s} | {'Bridge':>8s} {'Control':>8s}  | {'Bridge':>8s} {'Control':>8s}  |")
print(f"  {'-'*68}")
for pk in PRIM_KEYS:
    b_op = f"T{b_first_op[pk]}" if pk in b_first_op else "never"
    c_op = f"T{c_first_op[pk]}" if pk in c_first_op else "never"
    b_pr = f"T{b_first_pr[pk]}" if pk in b_first_pr else "never"
    c_pr = f"T{c_first_pr[pk]}" if pk in c_first_pr else "never"
    
    # Highlight if bridge is faster
    faster = ""
    if pk in b_first_op and pk in c_first_op:
        if b_first_op[pk] < c_first_op[pk]:
            faster = " ← bridge faster"
        elif c_first_op[pk] < b_first_op[pk]:
            faster = " ← control faster"
    elif pk in b_first_op and pk not in c_first_op:
        faster = " ← bridge ONLY"
    elif pk not in b_first_op and pk in c_first_op:
        faster = " ← control ONLY"
    
    print(f"  {pk:<16s} | {b_op:>8s} {c_op:>8s}  | {b_pr:>8s} {c_pr:>8s}  |{faster}")

# Element score trajectories
print(f"\n  Score trajectories (per turn):")
print(f"  {'Element':<16s} | {'Bridge (T1-T9)':^30s} | {'Control (T1-T9)':^30s}")
print(f"  {'-'*78}")
for pk in PRIM_KEYS:
    b_str = " ".join(f"{s:.1f}" for s in b_traj[pk])
    c_str = " ".join(f"{s:.1f}" for s in c_traj[pk])
    print(f"  {pk:<16s} | {b_str:^30s} | {c_str:^30s}")

# Stability analysis: how often does operative status persist once achieved?
print(f"\n  Operative persistence (once reached, stays operative in next turn?):")
for pk in PRIM_KEYS:
    for label, traj in [("Bridge", b_traj[pk]), ("Control", c_traj[pk])]:
        transitions = []
        for i in range(1, len(traj)):
            if traj[i-1] >= 1.0 and traj[i] < 1.0:
                transitions.append(f"T{i}→T{i+1}:drop")
            elif traj[i-1] < 1.0 and traj[i] >= 1.0:
                transitions.append(f"T{i}→T{i+1}:rise")
        if transitions:
            print(f"    {pk:<16s} [{label:7s}]: {', '.join(transitions)}")

# Summary stats
print(f"\n  Summary:")
b_total_op = sum(sum(1 for s in b_traj[pk] if s >= 1.0) for pk in PRIM_KEYS)
c_total_op = sum(sum(1 for s in c_traj[pk] if s >= 1.0) for pk in PRIM_KEYS)
b_total_labels = sum(sum(1 for s in b_traj[pk] if 0 < s < 1.0) for pk in PRIM_KEYS)
c_total_labels = sum(sum(1 for s in c_traj[pk] if 0 < s < 1.0) for pk in PRIM_KEYS)
print(f"    Total operative element-turns: Bridge={b_total_op}, Control={c_total_op} (delta={b_total_op-c_total_op:+d})")
print(f"    Total label element-turns:     Bridge={b_total_labels}, Control={c_total_labels} (delta={b_total_labels-c_total_labels:+d})")
print(f"    Rate operative element-turns:  Bridge={sum(1 for s in b_traj['rate'] if s>=1.0)}, Control={sum(1 for s in c_traj['rate'] if s>=1.0)}")
