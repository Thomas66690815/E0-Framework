"""Analyze session 6da717 — score each turn for Rate and element-level detail."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments.quality_metrics import score_e0_completeness

# Find the session file
session_file = None
for f in os.listdir('sessions'):
    if '6da717' in f:
        session_file = os.path.join('sessions', f)
        break

if not session_file:
    print("Session 6da717 not found!")
    sys.exit(1)

with open(session_file, 'r', encoding='utf-8') as fh:
    data = json.load(fh)

state = data.get('state', {})
history = state.get('history', [])
observations = data.get('observations', [])

# History is alternating: [canon, response, prompt, response, ...]
# Extract response texts (odd indices)
responses = [history[i] for i in range(1, len(history), 2)]

print(f"Session: {os.path.basename(session_file)}")
print(f"History entries: {len(history)}")
print(f"Responses: {len(responses)}")
print(f"Observations: {len(observations)}")
print("=" * 80)

d_values = []
for i, resp in enumerate(responses, 1):
    comp = score_e0_completeness(resp)
    d = comp['completeness']
    d_values.append(d)
    
    scores = comp.get('primitive_scores', {})
    detail = comp.get('detail', {})
    operative = [k for k, v in scores.items() if v >= 1.0]
    semi = [k for k, v in scores.items() if 0.75 <= v < 1.0]
    label = [k for k, v in scores.items() if 0 < v < 0.75]
    absent = [k for k, v in scores.items() if v == 0]
    
    rate_score = scores.get('rate', 0)
    rate_class = detail.get('rate', {}).get('status', 'absent')
    
    # Try to determine turn type from prompt
    prompt = history[max(0, (i-1)*2)] if (i-1)*2 < len(history) else '?'
    prompt_hint = prompt[:80].replace('\n', ' ')
    
    print(f"\nT{i} [D={d:.3f}] Rate={rate_class}({rate_score})")
    print(f"  Prompt: {prompt_hint}...")
    print(f"  Operative({len(operative)}): {operative}")
    if semi: print(f"  Semi({len(semi)}):      {semi}")
    if label: print(f"  Label({len(label)}):     {label}")
    if absent: print(f"  Absent({len(absent)}):    {absent}")

print("\n" + "=" * 80)
print("D trajectory:", [round(d, 3) for d in d_values])
if len(d_values) >= 2:
    # Skip T1 (canon init), analyze T2+ as module/reflect alternation
    module_d = [d_values[i] for i in range(1, len(d_values), 2)]  # T2, T4, T6, T8 = modules
    reflect_d = [d_values[i] for i in range(2, len(d_values), 2)]  # T3, T5, T7, T9 = reflects
    if module_d:
        print(f"Module avg D:  {sum(module_d)/len(module_d):.3f} ({module_d})")
    if reflect_d:
        print(f"Reflect avg D: {sum(reflect_d)/len(reflect_d):.3f} ({reflect_d})")
    rate_present = []
    for i, resp in enumerate(responses):
        comp = score_e0_completeness(resp)
        rate_s = comp['primitive_scores'].get('rate', 0)
        if rate_s > 0:
            rate_present.append(f"T{i+1}({rate_s})")
    print(f"Rate present in: {rate_present if rate_present else 'NONE'}")
    d1000 = sum(1 for d in d_values if d >= 0.999)
    print(f"D=1.000 turns: {d1000}")
    print(f"Max D: {max(d_values):.3f}, Min D: {min(d_values):.3f}")
