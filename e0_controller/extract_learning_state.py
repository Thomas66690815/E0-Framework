"""One-shot: extract learning data from bootstrap.json → learning_state.json."""
import json

with open("bootstrap.json", encoding="utf-8") as f:
    bs = json.load(f)

# Extract sections
ls = {
    "_meta": {
        "purpose": "Learning state for E₀ self-navigation. Separated from bootstrap.json (C203) to keep identity file lean.",
        "created": "2026-04-10",
        "source": "Extracted from bootstrap.json discovered_edges + cross_domain_bridges",
    },
    "discovered_edges": bs.pop("discovered_edges"),
    "cross_domain_bridges": bs.pop("cross_domain_bridges"),
}

# Add reference in bootstrap.json
bs["learning_state"] = {
    "_comment": "Learning data (discovered edges, cross-domain bridges, learning history) lives in learning_state.json. Kept separate to prevent identity file bloat from iterative exploration.",
    "file": "learning_state.json",
    "summary": {
        "discovered_edges": len(ls["discovered_edges"]["edges"]),
        "cross_domain_bridges": len(ls["cross_domain_bridges"]["bridges"]),
        "last_coverage": 0.962,
        "last_T_s": 0.049,
    },
}

# Write both
with open("learning_state.json", "w", encoding="utf-8") as f:
    json.dump(ls, f, indent=2, ensure_ascii=False)
    f.write("\n")

with open("bootstrap.json", "w", encoding="utf-8") as f:
    json.dump(bs, f, indent=2, ensure_ascii=False)
    f.write("\n")

n_edges = len(ls["discovered_edges"]["edges"])
n_bridges = len(ls["cross_domain_bridges"]["bridges"])
print(f"learning_state.json: {n_edges} edges, {n_bridges} bridges")
print(f"bootstrap.json: learning_state reference added, sections removed")
