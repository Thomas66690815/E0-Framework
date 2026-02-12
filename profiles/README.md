# E₀ Initialization Profiles

A profile defines a complete initialization path -- from model selection
through canon absorption to domain-specific structural priming.

The path mirrors E₀ itself:

```
Prerequisites → Canon → R̄ Verification → Domain Primers → Readiness
     ↓             ↓          ↓                ↓              ↓
  (states)    (differences)  (path check)  (historization)  (rate > 0)
```

Each step is structurally enforced. Each step is self-verifying via R̄.

## Usage

```
py e0_start.py --profile profiles/agriculture.json --api KEY
py e0_start.py --profile profiles/health.json --api KEY --web
py e0_start.py --profile profiles/default.json          # local GPT-2
```

The `--profile` flag overrides `--model`, `--lang`, and `--web` with values
from the profile. You still need `--api KEY` for API models.

## Schema

```json
{
  "name": "Profile Name",
  "description": "What this profile initializes and why.",

  "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
  "language": "en",

  "canon_r_threshold": 0.5,

  "primers": [
    {
      "name": "Step name (shown during initialization)",
      "prompt": "The structural text fed to the model after the canon.",
      "r_threshold": 0.8
    }
  ],

  "readiness_r": 0.5,
  "interface": "web"
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Display name for the profile |
| `description` | yes | What the profile does |
| `model` | yes | Model identifier (HuggingFace or API model name) |
| `language` | yes | `en` or `de` (guidance language) |
| `canon_r_threshold` | yes | Maximum R̄ after canon feed. If exceeded, system retries. |
| `primers` | yes | Array of domain-specific structural primers (can be empty) |
| `primers[].name` | yes | Step name shown during initialization |
| `primers[].prompt` | yes | Structural text fed to the model |
| `primers[].r_threshold` | yes | Maximum R̄ after this primer. Gate for next step. |
| `readiness_r` | yes | Final R̄ threshold. Below this = system ready. |
| `interface` | yes | `web` or `terminal` |

### R̄ Thresholds

The thresholds are structural gates. The system proceeds only when R̄
drops below the threshold. This mirrors E₀: a transition occurs only
when a path with finite resistance exists.

Recommended values:
- `canon_r_threshold`: 0.5 for 70B+, 1.0 for 7B, 2.0 for GPT-2
- `primers[].r_threshold`: 0.8 (primers are simpler than the full canon)
- `readiness_r`: 0.5 for 70B+, 1.0 for 7B

### Creating a New Profile

1. Copy `default.json`
2. Change `name`, `description`
3. Add domain-specific primers
4. Each primer should map E₀ primitives to the domain:
   - What is a **state** in this domain?
   - What is the **difference** that drives transitions?
   - What are the **paths** (admissible transitions)?
   - What determines **resistance**?
   - How does **historization** work?
5. Test with `--profile your-profile.json --api KEY`
6. Watch R̄ at each step. Adjust thresholds and prompts if needed.

## Available Profiles

| Profile | Domain | Primers | Description |
|---------|--------|---------|-------------|
| `default.json` | General | 0 | Canon only, no domain layer |
| `agriculture.json` | Agriculture | 3 | Fields, crops, soil, seasons |
| `health.json` | Health | 3 | Body states, triage, recovery |
| `water.json` | Water | 3 | Flow, infrastructure, distribution |
| `micro-economy.json` | Economy | 3 | Markets, trade, persistence |
| `education.json` | Education | 3 | Learning, curriculum, mastery |

## The Structural Parallel

The profile initialization is itself an E₀ process:

- The **state** is the model before initialization
- The **difference** is the gap between untrained and structurally aligned
- The **path** is the profile's primer sequence
- The **resistance** is R̄ (what we measure)
- The **historization** is what each primer does to the model's context
- The **time** is the ordering of primers
- The **rate** is how fast R̄ drops

When R̄ drops below the readiness threshold, the initialization
transition is complete. The system is ready.
