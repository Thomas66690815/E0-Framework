#!/usr/bin/env python3
"""
E₀ C132 — LLM-Enriched Canon Experiment
==========================================

Hypothesis: The learning plateau (52% seed for 59% coverage) is caused
by insufficient canon topology (avg degree 2.9, only 2 relation types).
Node fingerprints are not locally unique → bootstrap cannot discriminate
structurally similar words.

Solution: Use an LLM as "parent" (Elternteil) to generate rich, typed
semantic relations between the same 44 words. This creates unique
structural fingerprints per node — like going from 15-month-old babble
to 5-year-old structured language.

The LLM knows HOW words relate ("eyes are for seeing", "hot opposes cold",
"you eat with your mouth"). It provides this knowledge as canon structure.
The bootstrap then uses this structure to let the two languages "teach
each other" — symmetrically, without direct translation.

Experiment:
  1. Call LLM to generate typed edges for EN and DE separately
  2. Build enriched canon files (v2.0-enriched)
  3. Run Config B (11 seed pairs) on enriched canons
  4. Compare with v1.1 baseline (13 firm from C131b)

Key metric: Can we get >60% firm with only 25% seed (11/44)?
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")

from e0_controller.llm_adapter import LLMConfig, openai_call
from e0_controller.explore_dict_learning import (
    GROUND_TRUTH, config_b, learn_landscape,
)
from e0_controller.explore_level3_learning import (
    build_neighbor_map, PROMOTION_VOTES, MIN_CONTEXT_SCORE,
)
from e0_controller.explore_confidence_learning import (
    ConfidenceEntry, ConfidenceDictionary,
    extract_confidence_correspondences,
    compute_role_context_score,
    make_context_l2_execute_conf,
)
from e0_controller.dream_mode import (
    domain_fingerprints, find_equivalences,
)
from e0_controller.canon_loader import CANON_DIR


# ══════════════════════════════════════════════
# Relation types and delta mapping
# ══════════════════════════════════════════════

# Each type gets a unique delta so edges are metrically distinguishable.
# The delta encodes "conceptual distance" — part_of is close, opposite is far.
RELATION_DELTAS = {
    "part_of":     0.15,   # meronymy: finger→hand, eye→head
    "is_a":        0.20,   # category: apple→fruit, body→thing
    "located_in":  0.25,   # spatial: food→mouth, water→body
    "property_of": 0.30,   # attribute: cold→water, good→food
    "acts_on":     0.35,   # object: eat→food, see→thing
    "agent":       0.40,   # performer: self→see, self→eat
    "instrument":  0.45,   # tool: eat→mouth, see→eye
    "opposite_of": 0.50,   # antonym: hot↔cold, good↔bad
    "enables":     0.55,   # functional: eye→see, ear→hear
    "co_occurs":   0.35,   # collocational: make→new, take→hand
}

# Resistance mapping — tighter for structural, looser for associative
RELATION_RESISTANCE = {
    "part_of": 0.2, "is_a": 0.2, "located_in": 0.3,
    "property_of": 0.3, "acts_on": 0.3, "agent": 0.3,
    "instrument": 0.3, "opposite_of": 0.4, "enables": 0.2,
    "co_occurs": 0.4,
}

# ══════════════════════════════════════════════
# Word lists (from existing canons)
# ══════════════════════════════════════════════

EN_WORDS = [
    "thing", "action", "quality", "relation", "body", "food", "self",
    "head", "hand", "arm", "foot", "eye", "mouth", "ear", "finger",
    "water", "bread", "fruit", "apple", "milk", "salt",
    "go", "come", "see", "hear", "eat", "drink", "give", "take", "make", "say",
    "good", "bad", "big", "small", "hot", "cold", "new", "old",
    "in", "with", "from", "not", "all",
]

DE_WORDS = [
    "ding", "handlung", "eigenschaft", "beziehung", "koerper", "essen_n", "selbst",
    "kopf", "hand", "arm", "fuss", "auge", "mund", "ohr", "finger",
    "wasser", "brot", "frucht", "apfel", "milch", "salz",
    "gehen", "kommen", "sehen", "hoeren", "essen_v", "trinken", "geben", "nehmen", "machen", "sagen",
    "gut", "schlecht", "gross", "klein", "heiss", "kalt", "neu", "alt",
    "in_de", "mit", "von", "nicht", "alle",
]

# Human-readable labels for DE IDs (helps the LLM understand)
DE_LABELS = {
    "ding": "Ding (thing)", "handlung": "Handlung (action)",
    "eigenschaft": "Eigenschaft (quality)", "beziehung": "Beziehung (relation)",
    "koerper": "Körper (body)", "essen_n": "Essen [noun] (food)",
    "selbst": "Selbst (self)", "kopf": "Kopf (head)",
    "hand": "Hand", "arm": "Arm", "fuss": "Fuß (foot)",
    "auge": "Auge (eye)", "mund": "Mund (mouth)", "ohr": "Ohr (ear)",
    "finger": "Finger", "wasser": "Wasser (water)", "brot": "Brot (bread)",
    "frucht": "Frucht (fruit)", "apfel": "Apfel (apple)", "milch": "Milch (milk)",
    "salz": "Salz (salt)", "gehen": "gehen (to go)", "kommen": "kommen (to come)",
    "sehen": "sehen (to see)", "hoeren": "hören (to hear)",
    "essen_v": "essen [verb] (to eat)", "trinken": "trinken (to drink)",
    "geben": "geben (to give)", "nehmen": "nehmen (to take)",
    "machen": "machen (to make)", "sagen": "sagen (to say)",
    "gut": "gut (good)", "schlecht": "schlecht (bad)",
    "gross": "groß (big)", "klein": "klein (small)",
    "heiss": "heiß (hot)", "kalt": "kalt (cold)",
    "neu": "neu (new)", "alt": "alt (old)",
    "in_de": "in (spatial)", "mit": "mit (with)",
    "von": "von (from)", "nicht": "nicht (not)", "alle": "alle (all)",
}


# ══════════════════════════════════════════════
# LLM Prompt
# ══════════════════════════════════════════════

SYSTEM_PROMPT = """\
You are a linguist creating a semantic knowledge graph for language learning.
Your goal: define meaningful relationships between basic vocabulary words
so that EACH word has a unique "structural fingerprint" — identifiable
just by looking at its connections, like a person identifiable by their
network of friends.

Think of yourself as a parent explaining to a 5-year-old how words relate:
"Eyes are for seeing. You eat with your mouth. Hot is the opposite of cold.
Fingers are part of the hand."

Output ONLY valid JSON. No commentary, no markdown."""

def make_user_prompt(words: list, labels: dict = None, language: str = "English") -> str:
    """Build the user prompt for edge generation."""
    if labels:
        word_list = "\n".join(f"  {wid}: {labels[wid]}" for wid in words)
    else:
        word_list = ", ".join(words)

    rel_desc = "\n".join(
        f"  - {rtype} (delta={delta}): e.g. ..."
        for rtype, delta in RELATION_DELTAS.items()
    )

    return f"""\
Create a semantic knowledge graph for these 44 {language} words:
{word_list}

Use EXACTLY these relationship types:
  - part_of: X is a physical part of Y (finger part_of hand)
  - is_a: X is a type/category of Y (apple is_a fruit, body is_a thing)
  - located_in: X is typically found in/on Y (food located_in mouth when eating)
  - property_of: X is a typical property of Y (cold property_of water)
  - acts_on: action X typically targets Y (eat acts_on food, see acts_on thing)
  - agent: X typically performs action Y (self agent see, self agent eat)
  - instrument: action X is done using body part Y (eat instrument mouth)
  - opposite_of: X is the semantic opposite of Y (hot opposite_of cold)
  - enables: body part X enables action Y (eye enables see)
  - co_occurs: X and Y frequently occur together in {language} (make co_occurs new)

Rules:
1. Use ONLY the word IDs listed above — no new words, no synonyms
2. Each relation is DIRECTED: {{"source": "X", "target": "Y"}}
3. Every word must appear in at least 4 edges (as source or target)
4. Include CROSS-DOMAIN links: body parts ↔ actions, food ↔ qualities,
   abstract concepts ↔ concrete words
5. Include {language}-specific associations and collocations
6. Target 130-170 edges total
7. Do NOT duplicate: each (source, target, type) triple only once
8. opposite_of edges should appear only once per pair (hot→cold, not also cold→hot)

Output format:
{{"edges": [{{"source": "...", "target": "...", "type": "..."}}, ...]}}"""


# ══════════════════════════════════════════════
# LLM call + parse
# ══════════════════════════════════════════════

def call_llm_for_edges(
    words: list,
    labels: dict = None,
    language: str = "English",
    config: LLMConfig = None,
) -> List[Dict[str, str]]:
    """Call LLM to generate semantic edges. Returns list of edge dicts."""
    if config is None:
        config = LLMConfig(temperature=0.3, max_tokens=8192)

    prompt = make_user_prompt(words, labels, language)
    print(f"\n  Calling LLM for {language} edges...")
    print(f"  Model: {config.model}, T={config.temperature}")

    raw = openai_call(SYSTEM_PROMPT, prompt, config)

    # Parse JSON — handle potential markdown fencing
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]  # remove first line
        if text.endswith("```"):
            text = text[:-3]

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  ERROR: Failed to parse LLM response as JSON: {e}")
        print(f"  Raw response (first 500 chars): {raw[:500]}")
        raise

    edges = data.get("edges", data if isinstance(data, list) else [])
    return edges


def validate_edges(
    edges: List[Dict[str, str]],
    valid_words: Set[str],
    language: str,
) -> List[Dict[str, str]]:
    """Validate and filter LLM-generated edges.

    Deduplicates by (source, target) — the bootstrapper requires unique
    directed edges. When multiple types exist for the same pair, keeps
    the first one (usually the most specific).
    """
    valid_types = set(RELATION_DELTAS.keys())
    clean = []
    rejected = 0
    seen_triple = set()  # (src, tgt, type)
    seen_pair = set()    # (src, tgt) — bootstrapper constraint

    for e in edges:
        src = e.get("source", "")
        tgt = e.get("target", "")
        rtype = e.get("type", "")

        # Reject invalid
        if src not in valid_words:
            rejected += 1
            continue
        if tgt not in valid_words:
            rejected += 1
            continue
        if rtype not in valid_types:
            rejected += 1
            continue
        if src == tgt:
            rejected += 1
            continue

        # Deduplicate by triple
        triple = (src, tgt, rtype)
        if triple in seen_triple:
            continue
        seen_triple.add(triple)

        # Deduplicate by pair (bootstrapper requires unique src→tgt)
        pair = (src, tgt)
        if pair in seen_pair:
            continue
        seen_pair.add(pair)

        clean.append(e)

    n_dup = len(edges) - len(clean) - rejected
    print(f"  {language}: {len(clean)} valid edges "
          f"({rejected} rejected, {n_dup} duplicates/same-pair)")
    return clean


# ══════════════════════════════════════════════
# Build enriched canon JSON
# ══════════════════════════════════════════════

def build_enriched_canon(
    base_canon_name: str,
    llm_edges: List[Dict[str, str]],
    language: str,
) -> Dict[str, Any]:
    """Build enriched canon JSON from base canon + LLM edges."""
    # Load base canon for node definitions
    from e0_controller.canon_loader import load_canon_spec
    base = load_canon_spec(base_canon_name)

    # Keep all nodes
    nodes = base["nodes"]
    node_ids = {n["id"] for n in nodes}

    # Build new edge list from LLM output
    edges = []
    type_counts = {}
    for e in llm_edges:
        rtype = e["type"]
        delta = RELATION_DELTAS[rtype]
        resistance = RELATION_RESISTANCE[rtype]
        type_counts[rtype] = type_counts.get(rtype, 0) + 1
        edges.append({
            "from": e["source"],
            "to": e["target"],
            "delta": delta,
            "resistance": resistance,
            "initial_U": 2,
            "initial_F": 1,
            "type": rtype,
            "derivation": f"{e['source']} {rtype} {e['target']}",
        })

    # Degree analysis
    degree = {}
    for e in edges:
        degree[e["from"]] = degree.get(e["from"], 0) + 1
        degree[e["to"]] = degree.get(e["to"], 0) + 1
    avg_deg = sum(degree.values()) / max(len(degree), 1)
    min_deg = min(degree.values()) if degree else 0
    zero_nodes = node_ids - set(degree.keys())

    print(f"\n  {language} enriched canon:")
    print(f"    {len(nodes)} nodes, {len(edges)} edges")
    print(f"    Avg degree: {avg_deg:.1f} (was 2.9)")
    print(f"    Min degree: {min_deg} (was 1)")
    print(f"    Zero-degree nodes: {sorted(zero_nodes) if zero_nodes else 'none'}")
    print(f"    Edge types: {dict(sorted(type_counts.items()))}")

    enriched = {
        "name": f"{base_canon_name}_enriched",
        "version": "2.0-enriched",
        "source": "E0 C132 LLM Canon Enrichment",
        "description": (
            f"LLM-enriched {language} vocabulary — {len(nodes)} nodes, "
            f"{len(edges)} edges, {len(type_counts)} relation types. "
            f"Avg degree {avg_deg:.1f}. Generated by GPT for structural "
            f"fingerprint uniqueness."
        ),
        "nodes": nodes,
        "edges": edges,
        "goal_states": base.get("goal_states", []),
        "necessary_consequences": [
            f"Enriched with {len(type_counts)} typed relations from LLM",
            f"Avg degree {avg_deg:.1f} (vs 2.9 in v1.1) enables unique fingerprints",
            f"Cross-domain edges connect body↔action, food↔quality clusters",
        ],
    }
    return enriched


def save_enriched_canon(canon_data: Dict, filename: str):
    """Save enriched canon to canons/ directory."""
    path = CANON_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(canon_data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {path}")


# ══════════════════════════════════════════════
# Bootstrap on enriched canons
# ══════════════════════════════════════════════

def init_confidence_enriched(config_fn, label: str) -> ConfidenceDictionary:
    """Create ConfidenceDictionary using enriched canon neighbor maps."""
    en_nbrs = build_neighbor_map("english_basic_enriched")
    de_nbrs = build_neighbor_map("german_basic_enriched")
    cd = ConfidenceDictionary(en_neighbors=en_nbrs, de_neighbors=de_nbrs)
    pairs = config_fn()
    n_pairs = 0
    for d in pairs:
        for en, de in d.translations.items():
            key = f"{en}:{de}"
            cd.entries[key] = ConfidenceEntry(
                en=en, de=de, tier='canonical',
                cumulative_conf=0, raw_votes=0,
                rounds_seen=0, first_round=0, last_round=0,
                topo_score=1.0, role_score=1.0,
            )
            n_pairs += 1
    print(f"  {label}: {n_pairs} canonical pairs")
    return cd


def run_round_enriched(
    round_nr: int,
    cd: ConfidenceDictionary,
    verbose: bool = True,
) -> List[Tuple[str, str, float, float, int]]:
    """Run one learning round on enriched canons."""
    firm_en = cd.firm_en
    firm_de = cd.firm_de
    unknown_pairs = {
        en: de for en, de in GROUND_TRUTH.items()
        if en not in firm_en and de not in firm_de
    }

    cd.update_context_scores()

    if verbose:
        print(f"\n{'─'*72}")
        print(f"  Round {round_nr}: {cd.tier_summary()}")
        print(f"  Firm: {sorted(firm_en)}")
        tent = sorted(
            [e for e in cd.entries.values() if e.tier == 'tentative'],
            key=lambda e: -e.cumulative_conf,
        )
        if tent:
            print(f"  Tentative ({len(tent)}):")
            for e in tent[:10]:
                ctx_s = (f"{e.combined_context:.0%}"
                         if e.combined_context is not None else "?")
                correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
                print(f"    {e.en:>10}↔{e.de:<14} "
                      f"conf={e.cumulative_conf:>5.1f}({e.raw_votes}v) "
                      f"ew={e.effective_weight:.2f} ctx={ctx_s} {correct}")
            if len(tent) > 10:
                print(f"    ... and {len(tent)-10} more")
        conf = [(e.en, e.de) for e in cd.entries.values()
                if e.tier == 'confirmed']
        if conf:
            print(f"  Confirmed: {conf}")
        print(f"  Unknown remaining: {len(unknown_pairs)}")
        print(f"{'─'*72}")

    # Learn on ENRICHED canons
    en_exec = make_context_l2_execute_conf(cd, "en", seed=42 + round_nr)
    de_exec = make_context_l2_execute_conf(cd, "de", seed=143 + round_nr)
    en_L = learn_landscape("english_basic_enriched", en_exec, "EN")
    de_L = learn_landscape("german_basic_enriched", de_exec, "DE")

    cd.en_landscape = en_L
    cd.de_landscape = de_L

    if verbose:
        fps_en = domain_fingerprints(en_L, "EN")
        fps_de = domain_fingerprints(de_L, "DE")
        n_s_en = sum(1 for fp in fps_en if fp.quality > 0)
        n_s_de = sum(1 for fp in fps_de if fp.quality > 0)
        print(f"  EN: {n_s_en}S/{len(fps_en)-n_s_en}F edges  "
              f"DE: {n_s_de}S/{len(fps_de)-n_s_de}F edges")

    equivalences = find_equivalences(
        en_L, de_L,
        domain_a="EN", domain_b="DE",
        quantile=0.15,
    )

    if verbose:
        confs = [eq.confidence for eq in equivalences]
        if confs:
            avg_c = sum(confs) / len(confs)
            print(f"  Equivalences: {len(equivalences)}, "
                  f"avg confidence={avg_c:.3f}")

    discoveries = extract_confidence_correspondences(
        equivalences, firm_en, firm_de, min_confidence=0.5,
    )

    if verbose and discoveries:
        en2de, de2en = cd.build_translation_maps()
        print(f"\n  Discoveries:")
        print(f"  {'EN':<14} {'DE':<14} {'Conf':>6} {'Votes':>5} "
              f"{'Topo':>5} {'Role':>5}  Status")
        print(f"  {'─'*69}")

        for en, de, conf, avg_d, raw_v in discoveries:
            is_correct = GROUND_TRUTH.get(en) == de
            marker = "✓" if is_correct else "✗"
            topo, _, _, role = compute_role_context_score(
                en, de, en2de, de2en,
                cd.en_neighbors, cd.de_neighbors,
                en_L, de_L,
            )
            topo_s = f"{topo:.0%}" if topo is not None else "?"
            role_s = f"{role:.0%}" if role is not None else "?"
            key = f"{en}:{de}"
            existing = cd.entries.get(key)
            if existing and existing.tier == 'tentative':
                new_conf = existing.cumulative_conf + conf
                status = f"cum {existing.cumulative_conf:.1f}→{new_conf:.1f}"
            else:
                status = f"NEW conf={conf:.1f}"
            print(f"  {en:<14} {de:<14} {conf:>6.1f} {raw_v:>5} "
                  f"{topo_s:>5} {role_s:>5}  {marker} {status}")

    if verbose:
        correct = sum(1 for en, de, *_ in discoveries
                      if GROUND_TRUTH.get(en) == de)
        wrong = len(discoveries) - correct
        if correct + wrong > 0:
            print(f"\n  Accuracy: {correct}/{correct+wrong} "
                  f"({100*correct/(correct+wrong):.0f}%)")

    return discoveries


# ══════════════════════════════════════════════
# Coverage analysis
# ══════════════════════════════════════════════

def analyze_enriched_coverage(canon_name: str, seed_pairs: dict):
    """Analyze how much of the canon is reachable from seed."""
    from e0_controller.canon_loader import load_canon_spec
    spec = load_canon_spec(canon_name)

    # Build undirected adjacency
    adj = {}
    for e in spec["edges"]:
        adj.setdefault(e["from"], set()).add(e["to"])
        adj.setdefault(e["to"], set()).add(e["from"])

    all_nodes = {n["id"] for n in spec["nodes"]}
    seeded = set(seed_pairs.keys()) if "english" in canon_name else set(seed_pairs.values())

    # BFS from seeded nodes
    reachable = set(seeded)
    frontier = list(seeded)
    while frontier:
        node = frontier.pop()
        for nbr in adj.get(node, set()):
            if nbr not in reachable:
                reachable.add(nbr)
                frontier.append(nbr)

    # Nodes with translatable neighbors
    has_translated_nbr = set()
    for node in all_nodes:
        for nbr in adj.get(node, set()):
            if nbr in seeded:
                has_translated_nbr.add(node)
                break

    deserts = all_nodes - has_translated_nbr - seeded
    print(f"  {canon_name}: {len(all_nodes)} nodes, "
          f"{len(seeded)} seeded, "
          f"{len(reachable)} reachable ({len(reachable)/len(all_nodes)*100:.0f}%), "
          f"{len(deserts)} context deserts ({len(deserts)/len(all_nodes)*100:.0f}%)")


# ══════════════════════════════════════════════
# Main experiment
# ══════════════════════════════════════════════

def run_experiment(n_rounds: int = 10):
    """Full C132 experiment: LLM enrichment + bootstrap."""
    print("=" * 72)
    print("  E₀ C132 — LLM-Enriched Canon Experiment")
    print("=" * 72)

    # ── Step 1: Generate edges via LLM ──
    config = LLMConfig(temperature=0.3, max_tokens=8192)

    en_valid = set(EN_WORDS)
    de_valid = set(DE_WORDS)

    en_edges = call_llm_for_edges(EN_WORDS, language="English", config=config)
    en_edges = validate_edges(en_edges, en_valid, "EN")

    de_edges = call_llm_for_edges(DE_WORDS, labels=DE_LABELS, language="German", config=config)
    de_edges = validate_edges(de_edges, de_valid, "DE")

    # ── Step 2: Build enriched canons ──
    en_canon = build_enriched_canon("english_basic", en_edges, "English")
    de_canon = build_enriched_canon("german_basic", de_edges, "German")

    save_enriched_canon(en_canon, "english_basic_enriched.json")
    save_enriched_canon(de_canon, "german_basic_enriched.json")

    # ── Step 3: Coverage analysis ──
    print("\n  Coverage analysis (Config B seed on enriched canons):")
    seed_pairs = {}
    for d in config_b():
        seed_pairs.update(d.translations)
    analyze_enriched_coverage("english_basic_enriched", seed_pairs)
    analyze_enriched_coverage("german_basic_enriched", seed_pairs)

    print("\n  Coverage analysis (Config B seed on v1.1 canons):")
    analyze_enriched_coverage("english_basic", seed_pairs)
    analyze_enriched_coverage("german_basic", seed_pairs)

    # ── Step 4: Bootstrap on enriched canons ──
    label = "Config B + Enriched v2.0"
    cd = init_confidence_enriched(config_b, label)

    print(f"\n{'='*72}")
    print(f"  {label}: {cd.tier_summary()}")
    print(f"  Canons: v2.0-enriched (LLM-generated typed relations)")
    print(f"{'='*72}")

    for r in range(1, n_rounds + 1):
        discoveries = run_round_enriched(r, cd, verbose=(r <= 3 or r == n_rounds))

        # Integrate discoveries
        for en, de, conf, avg_d, raw_v in discoveries:
            key = f"{en}:{de}"
            if key in cd.entries:
                entry = cd.entries[key]
                entry.cumulative_conf += conf
                entry.raw_votes += raw_v
                entry.last_round = r
                entry.rounds_seen += 1
            else:
                en2de, de2en = cd.build_translation_maps()
                topo, _, _, role = compute_role_context_score(
                    en, de, en2de, de2en,
                    cd.en_neighbors, cd.de_neighbors,
                    cd.en_landscape, cd.de_landscape,
                )
                cd.entries[key] = ConfidenceEntry(
                    en=en, de=de, tier='tentative',
                    cumulative_conf=conf, raw_votes=raw_v,
                    rounds_seen=1, first_round=r, last_round=r,
                    topo_score=topo, role_score=role,
                )

        cd.update_context_scores()

        # Promote
        promoted = []
        for key, entry in list(cd.entries.items()):
            if entry.tier != 'tentative':
                continue
            if (entry.cumulative_conf >= PROMOTION_VOTES
                    and entry.combined_context is not None
                    and entry.combined_context >= MIN_CONTEXT_SCORE):
                entry.tier = 'confirmed'
                promoted.append((entry.en, entry.de))

        if promoted and (r <= 3 or r == n_rounds):
            print(f"\n  *** Promoted in R{r}: {promoted}")

    # ── Step 5: Final results ──
    print_results(cd, n_rounds)


def print_results(cd: ConfidenceDictionary, n_rounds: int):
    """Print final results summary."""
    c_count, t_count, f_count = cd.tier_counts()

    # Count correct/incorrect in each tier
    confirmed_correct = sum(
        1 for e in cd.entries.values()
        if e.tier == 'confirmed' and GROUND_TRUTH.get(e.en) == e.de
    )
    confirmed_total = sum(1 for e in cd.entries.values() if e.tier == 'confirmed')

    tent_correct = sum(
        1 for e in cd.entries.values()
        if e.tier == 'tentative' and GROUND_TRUTH.get(e.en) == e.de
    )
    tent_total = sum(1 for e in cd.entries.values() if e.tier == 'tentative')

    firm = c_count + confirmed_total + tent_correct
    total_disc = confirmed_total + tent_total
    disc_correct = confirmed_correct + tent_correct

    # Detailed tentative breakdown
    print(f"\n  After R{n_rounds}: {cd.tier_summary()}")
    for e in sorted(cd.entries.values(),
                    key=lambda x: (-1 if x.tier == 'confirmed' else 0, -x.cumulative_conf)):
        if e.tier == 'canonical':
            continue
        ctx_s = (f"{e.combined_context:.0%}"
                 if e.combined_context is not None else "?")
        correct = "✓" if GROUND_TRUTH.get(e.en) == e.de else "✗"
        print(f"     {e.tier:12s} {e.en:>12}↔{e.de:<14} "
              f"conf={e.cumulative_conf:>5.1f} ctx={ctx_s} {correct}")

    # relation↔beziehung status
    rel_key = "relation:beziehung"
    rel_entry = cd.entries.get(rel_key)
    if rel_entry:
        rel_status = f"{rel_entry.tier} conf={rel_entry.cumulative_conf:.0f} ctx="
        if rel_entry.combined_context is not None:
            rel_status += f"{rel_entry.combined_context:.0%}"
        else:
            rel_status += "?"
    else:
        rel_status = "not discovered"

    print(f"\n  {'─'*60}")
    print(f"  Config B + Enriched v2.0 RESULT: "
          f"{c_count}C + {confirmed_correct}/{confirmed_total}F "
          f"+ {tent_correct}/{tent_total}T = {firm} firm")
    print(f"  Discovery accuracy: {disc_correct}/{total_disc}")
    print(f"  relation↔beziehung: {rel_status}")
    print(f"  {'─'*60}")

    # Comparison with C131b baseline
    print(f"\n  {'='*60}")
    print(f"  COMPARISON with C131b baseline")
    print(f"  {'='*60}")
    print(f"  C131b Config B (v1.1): 11 seed → 13 firm (30%)")
    print(f"  C132  Config B (v2.0): 11 seed → {firm} firm ({firm/44*100:.0f}%)")
    print(f"  Improvement: +{firm - 13} firm pairs")
    print(f"  {'='*60}")


if __name__ == "__main__":
    run_experiment(n_rounds=10)
