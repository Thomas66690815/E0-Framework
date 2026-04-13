# Asymmetric Coupling: Practices and Observations from a 24-Day Human–AI Software Development Collaboration

**Version:** 1.0  
**Date:** 2026-04-13  
**Repository:** [E0-Framework](https://github.com/Thomas66690815/E0-Framework)  
**License:** CC BY 4.0  

---

## Abstract

This report documents the practices and quantitative observations from a 24-day collaboration between one human developer and one AI assistant (Claude, Anthropic) building the E₀-Framework — a decision-making system based on Ontodynamics. The collaboration produced 141,563 lines of Python across 309 files, with 5,006 tests, 175 distinct features, and a measured code churn of 2%. We identify five structural factors that contributed to sustained output, distinguish which factors are project-specific from those that generalize, and describe the functional roles that the human partner filled. The intent is not to claim novelty in Human–AI interaction research, but to provide a concrete, evidence-backed case study that other practitioners may find useful.

---

## 1. Scope and Limitations

**What this document is.** A retrospective analysis of one project's collaboration practices, grounded in git history and code metrics. All claims are verifiable from the public repository.

**What this document is not.** A controlled experiment. We have no control group, no A/B test, and no way to isolate individual factor contributions. The productivity numbers are descriptive, not causal. We also cannot separate human from AI contributions at the commit level — every commit was authored through the AI tool, directed by the human.

**Project characteristics that limit generalizability:**
- Greenfield development (no legacy constraints)
- Single domain (navigation under uncertainty)
- Library code only (no deployment, infrastructure, or operations)
- One human + one AI (no multi-person coordination overhead)
- No external deadlines or stakeholder reviews

These are favorable conditions. The practices described here may not transfer directly to maintenance-heavy, multi-team, or deadline-driven contexts.

---

## 2. Quantitative Summary

All figures are derived from the git history of `e0_controller/` between 2026-03-19 and 2026-04-11.

### 2.1 Output Metrics

| Metric | Value |
|--------|-------|
| Calendar days | 24 (all with commits, zero gaps) |
| Total commits | 298 |
| Distinct features (C-numbered) | 175 |
| Total lines (all `.py` files) | 141,563 |
| Effective lines (excl. blank/comment) | 107,752 |
| Production code | 32,456 lines (76 files) |
| Test code | 66,074 lines (137 files) |
| Exploration scripts | 34,860 lines (70 files) |
| Demo + benchmark code | 8,173 lines (26 files) |
| Test methods | 4,923 (96% unique names) |
| Test count (pytest collected) | 5,006 |
| Lines per test method | 13.4 |
| Test-to-production ratio | 2.0:1 (by lines) |

### 2.2 Quality Indicators

| Metric | Value | Note |
|--------|-------|------|
| Code churn | 2% | 156,910 lines added, 3,210 deleted across all commits |
| Falsified approaches | ≥4 | C127b, C132, C170, C171 — explicitly stopped and documented |
| Test suite regressions at HEAD | 0 | Green on 3 Python versions (3.11, 3.12, 3.13) |
| Documented failure patterns | 5 | Gordian Traps GT-1 through GT-5 in bootstrap.json |
| Refactoring commits | 4 | Minimal rewrite activity |

### 2.3 Rate Observations

| Metric | Observed | Industry reference |
|--------|----------|-------------------|
| Effective lines/day | 4,490 | Solo: 10–50 (McConnell), Team: 150–250 (Google internal estimates) |
| Features/day | 7.3 | — |
| Tests/commit | 16.8 | — |
| Commits/day | 12.4 | — |

**Caveat:** Lines of code is a poor productivity metric. We report it because it is the most verifiable measure available. The more meaningful observation is the combination of volume, test coverage, and low churn — suggesting that output was not generated carelessly.

---

## 3. Structural Factors

We identify five factors from the repository evidence and rank them by estimated contribution.

### 3.1 Narrow Interface Composition

The entire system rests on 3 definitions in `primitives.py` (43 lines): `Outcome` (2 values), `Edge` (2 fields), `TransportRegime` (3 modes). The `Landscape` class has 23 public methods. `Historization` has 4 core operations (`inscribe`, `trace_load`, `trace_quality`, `inertia_factor`).

218 of 309 files import `primitives`. 170 import `landscape`. Every feature — from Dream Mode to Multiverse to Perception to UI — composes the same small set of concepts. The 141K lines are not 141K distinct ideas; they are approximately 14 concepts applied in 175 different contexts.

**Implication for other projects:** A deliberately minimal core API enables high composability. Each new feature requires understanding only the interface, not the implementation of prior features. This is a well-known principle (information hiding, narrow interfaces), but the quantitative effect in a Human–AI context may be stronger than in human-only teams: the AI partner can hold the full interface in context at all times.

### 3.2 Bottom-Up Workflow

No feature was designed top-down. The consistent pattern was:

1. **Explore** — write an `explore_*.py` script to test a hypothesis
2. **Test** — if the hypothesis holds, write formal tests
3. **Formalize** — extract production code from the exploration
4. **Extend** — build the next feature on top

Evidence: 70 exploration scripts exist. At least 4 approaches were explicitly falsified (C127b cumulative vote bootstrap, C132 enriched topology, C170 partial structure matching, C171 asymmetric teaching). These falsifications were documented and committed — not silently abandoned.

**Effect:** Each commit is small enough to fit within a single AI context window. No commit depends on unverified assumptions from a prior session. The AI partner never needs to "trust" that a prior design decision was correct — it can verify from tests.

### 3.3 Consistent Domain Vocabulary

The quantum mechanics analogy (amplitude, phase, Born sampling, spinor, interference) provided a stable vocabulary across all domains. "Where is the high amplitude?" is a question that transfers immediately from chess to traffic simulation to invoice processing.

**This factor is partially E₀-specific.** The QM vocabulary works because the underlying theory (Ontodynamics) provides it. However, the generalizable principle is: any project benefits from a single, consistent metaphor set for its core operations. Without it, each new domain requires inventing new terminology, which increases coordination cost between human and AI.

### 3.4 Persistent Session Context (bootstrap.json)

Introduced at commit C120 (2026-04-03, day 15). A structured JSON file containing:
- Current project state (commit, test count, CI status)
- Reflexion traces (Gordian Traps with recurrence counts, Breakthroughs with dependency counts)
- Perspective Checks (questions to ask before committing to an approach, with trigger counts)
- Working conventions (commands, patterns, anti-patterns)

Commit rate before introduction: 11.6/day. After: 13.8/day (+19%). However, the primary effect is not speed but **error prevention across context windows**. The AI partner starts each session with full project context, including documented failure patterns. Without this, Gordian Trap GT-1 (Isolated Agents — 4 commits fixing symptoms instead of root cause) would likely have recurred.

**Directly transferable.** Any Human–AI collaboration with multi-session continuity benefits from a structured, machine-readable context file that the AI reads at session start.

### 3.5 Declarative Domain Specifications

Canon files (JSON, 15–60 KB) are purely declarative: nodes, edges, levels, relation types. The bootstrapper that converts a canon to a navigable Landscape is ~300 lines. Adding a new domain (e.g., C221 Mechanism Domain: 20 nodes, 43 edges) takes approximately 30 minutes including tests.

**This is a downstream effect of Factor 3.1.** The canons are simple because the primitives allow them to be. The transferable insight: if the core API is narrow enough, domain specifications become trivially small.

---

## 4. The Human Partner's Function

Since every commit was authored through the AI tool, the git log cannot separate contributions. However, three distinct human functions are identifiable from the collaboration pattern:

### 4.1 Direction Setting

The human partner determined *which questions to pursue*. The theoretical framework (Ontodynamics), the decision to use QM analogies, the bottom-up workflow principle, and the choice of when to stop a failing approach — these are directional decisions that the AI partner cannot originate, because they require values and goals external to the codebase.

**Observable evidence:** The 5 Gordian Traps and 4 Breakthroughs in bootstrap.json represent directional decisions — moments where the project could have continued in a wrong direction but was corrected.

### 4.2 Falsification Enforcement

The collaboration operated under an explicit norm: the AI's outputs must be falsifiable, and the human regularly challenged them. This manifests as:

- The instruction "do not simply accept my claims — verify them" appearing in multiple sessions
- External analyses from other AI systems being submitted for independent verification (3 claims checked, 1 confirmed correct, 1 partially correct, 1 false — all verified against code)
- The Perspective Checks mechanism, which forces explicit consideration of failure modes before implementation

**This is a cultural contribution, not a technical one.** Without it, the AI partner tends toward confirmation of the human's stated beliefs. The falsification norm counteracts this tendency.

### 4.3 Coherence Anchor Across Context Windows

Each AI session begins with zero memory. The human partner maintained continuity by:
- Updating bootstrap.json after each session
- Providing session summaries at context boundaries
- Maintaining trace counts (confirmed/contradicted/recurred) on working principles
- Correcting the AI when it drifted from established conventions

**This function diminishes if AI context persistence improves.** It is currently critical because the AI partner has no long-term memory. The bootstrap.json mechanism is a human-maintained prosthetic memory for the AI.

---

## 5. Error Correction Patterns

Five failure patterns were identified, documented, and resolved during the project. Each is logged as a "Gordian Trap" in bootstrap.json with recurrence tracking.

| ID | Pattern | Commits to Resolve | Lesson |
|----|---------|-------------------|--------|
| GT-1 | Isolated Agents | 4 (C185–C189) | When agents share a domain, check first: do they share knowledge? |
| GT-2 | Blind Trust | 3 (C172–C174) | Any signal the system relies on can be poisoned |
| GT-3 | Greedy Matching | 7 (C130–C137) | When incremental improvements stall, the bottleneck may not be where you think |
| GT-4 | Distance Collapse | 3 (C126–C128) | Self-modifying systems can destroy their own discrimination signal |
| GT-5 | Amplitude Override | 2 (C192–C193) | A mechanism that helps in one domain can hurt in another |

Average: 3.8 commits per failure pattern. The critical observation is that **none recurred after resolution** (all recurrence counts remain at 0). This suggests that explicit documentation of failure patterns, combined with a mechanism to check for recurrence, is effective at preventing repeated mistakes — even across AI context windows.

---

## 6. What We Cannot Claim

1. **Causality.** We cannot prove that any specific practice caused the observed output. The factors co-occurred; we cannot isolate them.

2. **Human contribution magnitude.** From the git log, 100% of code was authored by the AI tool. The human's contribution — direction, falsification, coherence — is structurally invisible in commit diffs. We acknowledge this asymmetry without resolving it.

3. **Generalizability beyond greenfield.** All observations come from a greenfield library project. Maintenance, legacy integration, and multi-team coordination introduce constraints not present here.

4. **Comparison validity.** Industry LOC/day benchmarks (McConnell, COCOMO) were established for human-only teams. Direct comparison with a Human–AI pair is methodologically unsound. We report both numbers for context, not as a ratio claim.

5. **Sustainability.** 24 days is a sprint, not a marathon. We have no evidence about whether these practices sustain over months.

---

## 7. Transferable Practices (Summary)

For practitioners who want to try similar approaches:

| Practice | Mechanism | Cost |
|----------|-----------|------|
| **Structured session bootstrap file** | JSON/YAML with project state, conventions, failure history. AI reads at session start. | ~30 min setup, ~5 min/session maintenance |
| **Bottom-up feature workflow** | Explore → Test → Formalize → Extend. Never commit untested assumptions. | Requires discipline to resist top-down design |
| **Explicit falsification norm** | Challenge AI outputs. Demand verification of claims. Log false positives. | Slower per-interaction; prevents compounding errors |
| **Narrow core API** | Keep the interface small enough that the AI can hold it entirely in context. | Upfront design effort; hard to retrofit |
| **Failure pattern tracking** | Document recurring mistakes with recurrence counts. Review before new features. | Marginal per-incident; high value over time |

---

## 8. Methodology Notes

**Data sources.** All quantitative claims derive from `git log`, `git diff --numstat`, line counting via `Get-Content`, and `pytest --collect-only`. No external tools or estimates were used.

**Line counting.** "Effective lines" excludes lines matching `^\s*$` (blank) or `^\s*#` (comment). Import lines, docstrings, and type annotations are included in the effective count.

**Churn calculation.** Total lines added and deleted across all commits touching `e0_controller/`. Churn = deleted / added. This understates true churn because in-place edits (replacing N lines with M lines) register as N deletions + M additions.

**Feature counting.** Each C-numbered commit represents one feature. Some features span multiple commits (amendments, fixes), but each C-number is counted once. The 175 count is derived from `git log --oneline | grep C\d+ | sort -u`.

**Test counting.** `pytest --collect-only` yields 5,006 test items. Test method count (4,923) is derived from `grep 'def test_'` across test files. The difference (83) comes from parametrized tests that expand one method into multiple test cases (plus 139 subtests from `subTest`).

---

## Appendix A: Repository Structure at Time of Writing

```
e0_controller/
  76 production modules (32,456 lines)
  137 test files (66,074 lines)
  70 exploration scripts (34,860 lines)
  17 demo scripts (5,114 lines)
  9 benchmark scripts (3,059 lines)

Core (primitives + landscape + controller + historization + self_graph):
  2,574 lines (7.9% of production code)

Everything else: compositions of the core.
```

## Appendix B: Commit Frequency Distribution

```
Date        Commits    Date        Commits
2026-03-19        6    2026-04-01        7
2026-03-20        5    2026-04-02       16
2026-03-21       10    2026-04-03       23  ← bootstrap.json introduced
2026-03-22        4    2026-04-04       22
2026-03-23        9    2026-04-05       21
2026-03-24        6    2026-04-06       15
2026-03-25       13    2026-04-07        1
2026-03-26       23    2026-04-08        6
2026-03-27       14    2026-04-09       14
2026-03-28       10    2026-04-10       16
2026-03-29        7    2026-04-11        6
2026-03-30       21
2026-03-31       23
                       Total: 298 commits
```

## Appendix C: Gordian Traps (Failure Pattern Registry)

Reproduced from bootstrap.json for reference. Each trap includes a recurrence count — the number of times the same pattern reappeared after initial resolution.

| ID | Name | When | Commits | Recurred |
|----|------|------|---------|----------|
| GT-1 | Isolated Agents | C185–C189 | 5 | 0 |
| GT-2 | Blind Trust | C172–C174 | 3 | 0 |
| GT-3 | Greedy Matching | C130–C137 | 8 | 0 |
| GT-4 | Distance Collapse | C126–C128 | 3 | 0 |
| GT-5 | Amplitude Override | C192–C193 | 2 | 0 |
