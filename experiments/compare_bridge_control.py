"""Compare bridge session (6da717) vs control session (23b99f) — element-level."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments.quality_metrics import score_e0_completeness

def analyze_session(session_id):
    """Load and score a session."""
    session_file = None
    for f in os.listdir('sessions'):
        if session_id in f:
            session_file = os.path.join('sessions', f)
            break
    if not session_file:
        print(f"Session {session_id} not found!")
        return None
    
    with open(session_file, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    
    state = data.get('state', {})
    history = state.get('history', [])
    responses = [history[i] for i in range(1, len(history), 2)]
    
    results = []
    for i, resp in enumerate(responses, 1):
        comp = score_e0_completeness(resp)
        scores = comp.get('primitive_scores', {})
        detail = comp.get('detail', {})
        results.append({
            'turn': i,
            'D': comp['completeness'],
            'scores': scores,
            'detail': detail,
            'rate': scores.get('rate', 0),
            'rate_status': detail.get('rate', {}).get('status', 'absent'),
        })
    return results

def print_session(name, results, topo_label):
    print(f"\n{'='*70}")
    print(f"  {name}  (topology={topo_label})")
    print(f"{'='*70}")
    d_vals = []
    rate_operative_turns = []
    for r in results:
        d_vals.append(r['D'])
        # Determine turn type: T1=canon, then alternating module/reflect
        # T1=canon, T2=ontodynamics, T3=reflect, T4=identity, T5=reflect, ...
        if r['turn'] == 1:
            ttype = "Canon"
        elif r['turn'] % 2 == 0:
            ttype = "Module"
        else:
            ttype = "Reflect"
        
        op = [k for k, v in r['scores'].items() if v >= 1.0]
        semi = [k for k, v in r['scores'].items() if 0.75 <= v < 1.0]
        lbl = [k for k, v in r['scores'].items() if 0 < v < 0.75]
        
        rate_mark = "**ρ**" if r['rate'] >= 1.0 else ("ρ?" if r['rate'] > 0 else "—")
        if r['rate'] >= 1.0:
            rate_operative_turns.append(r['turn'])
        
        print(f"  T{r['turn']:2d} [{ttype:7s}] D={r['D']:.3f}  Rate={rate_mark:4s}  Op={len(op)} Semi={len(semi)} Lbl={len(lbl)}")
    
    # Stats
    module_d = [d_vals[i] for i in range(1, len(d_vals), 2)]
    reflect_d = [d_vals[i] for i in range(2, len(d_vals), 2)]
    print(f"\n  Module avg D:  {sum(module_d)/len(module_d):.3f}  {[round(d,3) for d in module_d]}")
    print(f"  Reflect avg D: {sum(reflect_d)/len(reflect_d):.3f}  {[round(d,3) for d in reflect_d]}")
    print(f"  Overall avg D: {sum(d_vals)/len(d_vals):.3f}")
    print(f"  Amplitude:     {sum(reflect_d)/len(reflect_d) - sum(module_d)/len(module_d):.3f}")
    print(f"  Rate operative: T{rate_operative_turns}" if rate_operative_turns else "  Rate operative: NONE")
    
    return {
        'module_avg': sum(module_d)/len(module_d),
        'reflect_avg': sum(reflect_d)/len(reflect_d),
        'overall_avg': sum(d_vals)/len(d_vals),
        'amplitude': sum(reflect_d)/len(reflect_d) - sum(module_d)/len(module_d),
        'rate_operative_turns': rate_operative_turns,
        'd_vals': d_vals,
    }

# Analyze both sessions
bridge = analyze_session('6da717')
control = analyze_session('23b99f')

if bridge and control:
    b_stats = print_session("Bridge Session (6da717)", bridge, "YES")
    c_stats = print_session("Control Session (23b99f)", control, "NO")
    
    print(f"\n{'='*70}")
    print(f"  COMPARISON: Bridge vs Control")
    print(f"{'='*70}")
    print(f"  {'Metric':<25s} {'Bridge':>10s} {'Control':>10s} {'Delta':>10s}")
    print(f"  {'-'*55}")
    for label, bk, ck in [
        ('Module avg D', 'module_avg', 'module_avg'),
        ('Reflect avg D', 'reflect_avg', 'reflect_avg'),
        ('Overall avg D', 'overall_avg', 'overall_avg'),
        ('Amplitude (R-M)', 'amplitude', 'amplitude'),
    ]:
        bv = b_stats[bk]
        cv = c_stats[ck]
        print(f"  {label:<25s} {bv:>10.3f} {cv:>10.3f} {bv-cv:>+10.3f}")
    
    print(f"  {'Rate operative turns':<25s} {len(b_stats['rate_operative_turns']):>10d} {len(c_stats['rate_operative_turns']):>10d}")
    
    # Per-element comparison across all turns
    print(f"\n  Per-element mean score (all turns):")
    print(f"  {'Element':<20s} {'Bridge':>10s} {'Control':>10s} {'Delta':>10s}")
    print(f"  {'-'*50}")
    prim_keys = ['state', 'difference', 'path', 'resistance', 'historization', 'time', 'rate', 'axiom_a0']
    for pk in prim_keys:
        b_mean = sum(r['scores'].get(pk, 0) for r in bridge) / len(bridge)
        c_mean = sum(r['scores'].get(pk, 0) for r in control) / len(control)
        marker = " <<<" if abs(b_mean - c_mean) >= 0.15 else ""
        print(f"  {pk:<20s} {b_mean:>10.3f} {c_mean:>10.3f} {b_mean-c_mean:>+10.3f}{marker}")
