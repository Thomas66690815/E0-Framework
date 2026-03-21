# Scenario Packet Schema v0.1

**Status:** Draft  
**Purpose:** Standardized scenario inputs for E₀ open-domain validation  
**Scope:** Competitor Brief, Incident Postmortem, Research Brief, and future domains

---

## 1. Motivation

The current demos already contain concrete default tasks, but those tasks are embedded directly in demo scripts as free-text strings.

That is sufficient for demos, but not ideal for:

- repeatable validation,
- cross-domain comparison,
- scenario-level benchmarking,
- controlled evaluation of LLM-grounded behavior,
- future scenario libraries.

A **Scenario Packet** makes the scenario itself explicit and portable.

It separates:

1. **Scenario content**
2. **E₀ runtime context**
3. **Evaluation expectations**

---

## 2. Design Principle

A Scenario Packet is **not** the Landscape.
A Scenario Packet is **not** the MemOS snapshot.
A Scenario Packet is **not** the controller state.

It is the **domain-content carrier** that the LLM should receive as the semantic source material for a run.

Operationally:

```text
Scenario Packet
    +
E₀ Runtime Snapshot (MemOS summary)
    +
Output Discipline / Task Contract
    →
LLM prompt context
```

---

## 3. Minimal Required Fields

Each Scenario Packet must define the following fields.

### 3.1 `scenario_id`
Stable identifier.

Example:

```json
"scenario_id": "incident_payment_outage_001"
```

### 3.2 `domain`
The scenario family.

Examples:

- `competitor_brief`
- `incident_postmortem`
- `research_brief`

### 3.3 `title`
Human-readable scenario title.

### 3.4 `source_text`
The primary content the LLM must work from.

This is the most important semantic field.
It should contain the actual raw material:

- incident report,
- product announcement,
- paper abstract,
- customer complaint,
- etc.

### 3.5 `objective`
The explicit outcome requested from the scenario.

Example:

```json
"objective": "Produce a structured postmortem briefing"
```

### 3.6 `required_outputs`
List of output sections or semantic deliverables.

Example:

```json
"required_outputs": [
  "timeline",
  "trigger",
  "root_cause",
  "impact",
  "mitigations",
  "followups"
]
```

### 3.7 `known_constraints`
Scenario-specific constraints or limitations.

Examples:

- incomplete evidence,
- ambiguity allowed if labeled,
- do not invent missing data,
- remain grounded in source text.

### 3.8 `evaluation_points`
Human-readable criteria used to judge result quality.

These are not hard controller rules; they are evaluation anchors.

---

## 4. Optional Fields

### 4.1 `start_state`
Recommended starting state name for the domain.

### 4.2 `goal_state`
Recommended goal state name for the domain.

### 4.3 `expected_sections`
A more concrete structural output template.

### 4.4 `notes`
Free-form metadata or comments.

### 4.5 `metadata`
Machine-readable auxiliary information such as source, author, difficulty, date, or tags.

---

## 5. Canonical JSON Shape

```json
{
  "scenario_id": "<stable_id>",
  "domain": "<domain_name>",
  "title": "<human_title>",
  "source_text": "<raw semantic input>",
  "objective": "<requested goal>",
  "required_outputs": [
    "<section_1>",
    "<section_2>"
  ],
  "known_constraints": [
    "<constraint_1>",
    "<constraint_2>"
  ],
  "evaluation_points": [
    "<criterion_1>",
    "<criterion_2>"
  ],
  "start_state": "<optional_start_state>",
  "goal_state": "<optional_goal_state>",
  "expected_sections": [
    "<optional_section_1>",
    "<optional_section_2>"
  ],
  "notes": "<optional_notes>",
  "metadata": {
    "difficulty": "<optional>",
    "source_type": "<optional>",
    "date": "<optional>"
  }
}
```

---

## 6. What the LLM Should Receive

The LLM should not receive only free-text scenario content.

The full semantic context should be composed of three blocks.

### 6.1 Scenario Context
From the Scenario Packet:

- `title`
- `source_text`
- `objective`
- `required_outputs`
- `known_constraints`
- `expected_sections` (if present)

### 6.2 E₀ Runtime Context
From MemOS / live summary:

- `current_state`
- `admissible_neighbors`
- `edge_history`
- `recent_states`
- escalation context if relevant

### 6.3 Output Discipline Context
A strict instruction layer such as:

- remain grounded in the scenario packet,
- do not invent unstated evidence,
- mark uncertainty explicitly,
- return strict JSON only,
- align proposed output with the requested sections.

---

## 7. Relationship to Current Repo State

Scenario Packets should become the content input layer for the open-domain demos.

They should replace ad hoc embedded `DEFAULT_TASK` strings over time, or at minimum provide a structured alternative.

This would allow:

- multiple scenarios per domain,
- cross-run reproducibility,
- domain-level and scenario-level comparisons,
- future benchmark suites.

---

## 8. Recommended Repository Layout

```text
scenarios/
├── SCENARIO_PACKET_SCHEMA_v0.1.md
├── competitor_brief/
│   └── competitor_ai_launch_001.json
├── incident_postmortem/
│   └── incident_payment_outage_001.json
└── research_brief/
    └── research_low_resource_mt_001.json
```

---

## 9. Core Thesis

A domain is not yet a scenario.
A demo is not yet a reusable evaluation input.

Scenario Packets convert open-domain tests into structured, repeatable semantic inputs.

That is their purpose.

---

## End of Document
