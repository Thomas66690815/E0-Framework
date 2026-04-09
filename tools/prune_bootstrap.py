"""First structural entropy prune on bootstrap.json commit_history_recent."""
import json
import re

path = r"c:\.gitRepos\E0-Framework\bootstrap.json"

with open(path, "r", encoding="utf-8") as f:
    d = json.load(f)

# Collect all C-IDs referenced anywhere in reflexion/checks/context
refs_text = (
    json.dumps(d["reflexion"])
    + json.dumps(d["perspective_checks"])
    + json.dumps(d["active_context"])
)
c_ids = set(re.findall(r"C\d+[a-z]?", refs_text))

hist = d["commit_history_recent"]
print(f"Before prune: {len(hist)} entries")

# Keep: first 30 (most recent) + any entry whose id matches a referenced C-ID
recent = hist[:30]
recent_ids = set(e["id"] for e in recent)

anchored = []
for e in hist[30:]:
    eid = e["id"]
    is_anchored = any(c == eid or c in eid for c in c_ids)
    if is_anchored:
        anchored.append(e)

survivors = recent + anchored
print(f"Recent 30: {len(recent)}")
print(f"Anchored beyond 30: {len(anchored)}")
for a in anchored:
    title = a["title"][:60]
    print(f"  ANCHOR: {a['id']} - {title}")
print(f"After prune: {len(survivors)} entries")
print(f"Pruned: {len(hist) - len(survivors)} entries")

d["commit_history_recent"] = survivors
d["structural_entropy"]["sections"]["commit_history_recent"]["pruned_to"] = len(survivors)
d["structural_entropy"]["sections"]["commit_history_recent"]["current_count_at_last_prune"] = len(survivors)

with open(path, "w", encoding="utf-8") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
print("Written.")
