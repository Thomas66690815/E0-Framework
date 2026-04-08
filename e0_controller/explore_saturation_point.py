"""
C182 — Mesh Saturation Point Exploration

At what N does mesh quality collapse?  We scale the 5-domain mesh
(C180) to N ∈ {3, 5, 7, 10, 13, 16, 18} by adding bootstrapped
workflow domains from a parametric factory.

Quality metrics per N:
  - canon_cluster:     EN↔DE cluster still forms (bool)
  - bridge_count:      how many bootstrapped domains ONTO bridges to
  - de_isolation:      DE stays isolated from all bootstrapped domains
  - bootstrap_pairs:   compatible pairs within bootstrap family
  - mean_eq_per_pair:  avg dream equivalences per compatible pair
  - false_positives:   spurious equivalences between known-incompatible pairs
  - compat_separation: gap between best-incompatible and worst-compatible score
  - time_per_episode:  wall-clock seconds per mesh episode

Collapse indicators (any of):
  - EN↔DE cluster stops forming
  - ONTO bridge count drops to 0
  - DE gains spurious cross-family connections
  - false_positives > 0
  - mean_eq_per_pair drops below 50% of N=5 baseline
  - compat_separation < 0.05

Protocol:
  For each N in TEST_SIZES:
    Phase 1: Prepare N domains (3 canon + N-3 bootstrapped)
    Phase 2: Pre-nav compatibility matrix
    Phase 3: Mesh assembly + 8 episodes
    Phase 4: Post-nav compatibility matrix
    Phase 5: Measure quality metrics
    Phase 6: Aggregate and find collapse point

Reference: docs/E0_STRATEGIC_ROADMAP_v1.md Priority 3
"""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Tuple

from e0_controller.bootstrapper import bootstrap_landscape
from e0_controller.canon_loader import load_canon
from e0_controller.controller import E0Controller, HybridMode
from e0_controller.coupling_router import (
    CouplingRouter,
    Universe,
    update_weights_from_dream,
)
from e0_controller.curriculum import CurriculumRunner
from e0_controller.dream_mode import (
    DreamObserver,
    dream_compatibility,
)
from e0_controller.primitives import Outcome
from e0_controller.structural_entropy import (
    dream_pressure,
    structural_temperature,
)


# ── Configuration ────────────────────────────────────────────────────

EXEC_FN = lambda s, t: Outcome.SUCCESS

CANON_DOMAINS = [
    ("EN",   "english_basic_enriched",  "thing",      "self"),
    ("DE",   "german_basic_enriched",   "ding",       "selbst"),
    ("ONTO", "ontodynamics",            "difference", "negative_necessity"),
]

N_EPISODES = 8
MAX_CYCLES_PER_RUN = 40
COMPATIBILITY_THRESHOLD = 0.6

# N values to test: 3 canon + varying bootstrap count
TEST_SIZES = [3, 5, 7, 10, 13, 16, 18]


# ── Domain Factory ───────────────────────────────────────────────────

# Seed topologies: 15 bootstrapped workflow domains.
# Each has 10 nodes, 12-14 edges with varying delta/resistance profiles.
# The factory uses deterministic parameters derived from the domain name
# so results are fully reproducible.

DOMAIN_TEMPLATES = [
    {
        "label": "COOK",
        "nodes": ["RECIPE_SELECTION", "INGREDIENT_PREP", "COOKING_TECHNIQUE",
                  "FLAVOR_BALANCE", "PLATING", "TASTING", "ADJUSTMENT",
                  "SERVING", "CLEANUP", "PLANNING"],
        "start": "PLANNING", "goal": "SERVING",
        "edges": [
            ("RECIPE_SELECTION", "INGREDIENT_PREP",  0.7, 0.3, 8, 1, 0.9),
            ("INGREDIENT_PREP",  "COOKING_TECHNIQUE", 0.6, 0.5, 7, 2, 0.8),
            ("COOKING_TECHNIQUE","FLAVOR_BALANCE",    0.5, 0.6, 5, 3, 0.7),
            ("FLAVOR_BALANCE",   "TASTING",           0.4, 0.4, 6, 2, 0.8),
            ("TASTING",          "ADJUSTMENT",        0.3, 0.3, 4, 4, 0.5),
            ("ADJUSTMENT",       "COOKING_TECHNIQUE", 0.5, 0.7, 3, 3, 0.5),
            ("FLAVOR_BALANCE",   "PLATING",           0.6, 0.4, 7, 1, 0.9),
            ("PLATING",          "SERVING",           0.8, 0.2, 9, 0, 0.95),
            ("SERVING",          "CLEANUP",           0.3, 0.5, 5, 2, 0.7),
            ("PLANNING",         "RECIPE_SELECTION",  0.6, 0.4, 6, 1, 0.8),
            ("CLEANUP",          "PLANNING",          0.2, 0.6, 3, 1, 0.6),
            ("TASTING",          "PLATING",           0.5, 0.3, 6, 2, 0.7),
            ("RECIPE_SELECTION", "PLANNING",          0.3, 0.5, 4, 2, 0.6),
        ],
    },
    {
        "label": "PROJ",
        "nodes": ["REQUIREMENTS", "DESIGN", "IMPLEMENTATION", "TESTING",
                  "REVIEW", "DEPLOYMENT", "MONITORING", "FEEDBACK",
                  "PLANNING", "DOCUMENTATION"],
        "start": "PLANNING", "goal": "DEPLOYMENT",
        "edges": [
            ("REQUIREMENTS",    "DESIGN",          0.7, 0.4, 7, 2, 0.8),
            ("DESIGN",          "IMPLEMENTATION",  0.6, 0.5, 6, 3, 0.7),
            ("IMPLEMENTATION",  "TESTING",         0.5, 0.4, 5, 3, 0.7),
            ("TESTING",         "REVIEW",          0.4, 0.3, 6, 2, 0.8),
            ("REVIEW",          "DEPLOYMENT",      0.7, 0.3, 8, 1, 0.9),
            ("DEPLOYMENT",      "MONITORING",      0.3, 0.5, 5, 2, 0.7),
            ("MONITORING",      "FEEDBACK",        0.4, 0.4, 4, 3, 0.6),
            ("FEEDBACK",        "REQUIREMENTS",    0.5, 0.6, 3, 3, 0.5),
            ("PLANNING",        "REQUIREMENTS",    0.6, 0.3, 7, 1, 0.85),
            ("TESTING",         "IMPLEMENTATION",  0.4, 0.7, 2, 4, 0.5),
            ("REVIEW",          "DESIGN",          0.3, 0.6, 2, 3, 0.5),
            ("IMPLEMENTATION",  "DOCUMENTATION",   0.4, 0.4, 5, 2, 0.7),
            ("DOCUMENTATION",   "DEPLOYMENT",      0.3, 0.3, 6, 1, 0.8),
        ],
    },
    {
        "label": "SUPPLY",
        "nodes": ["SOURCING", "PROCUREMENT", "WAREHOUSE", "QUALITY_CHECK",
                  "INVENTORY", "LOGISTICS", "DELIVERY", "RETURNS",
                  "ANALYTICS", "PLANNING"],
        "start": "PLANNING", "goal": "DELIVERY",
        "edges": [
            ("SOURCING",       "PROCUREMENT",    0.6, 0.4, 7, 2, 0.8),
            ("PROCUREMENT",    "WAREHOUSE",      0.5, 0.3, 8, 1, 0.9),
            ("WAREHOUSE",      "QUALITY_CHECK",  0.4, 0.5, 5, 3, 0.7),
            ("QUALITY_CHECK",  "INVENTORY",      0.3, 0.3, 6, 2, 0.75),
            ("INVENTORY",      "LOGISTICS",      0.6, 0.4, 7, 1, 0.85),
            ("LOGISTICS",      "DELIVERY",       0.7, 0.2, 9, 0, 0.95),
            ("DELIVERY",       "RETURNS",        0.3, 0.6, 3, 4, 0.5),
            ("RETURNS",        "WAREHOUSE",      0.4, 0.5, 4, 3, 0.6),
            ("ANALYTICS",      "SOURCING",       0.5, 0.4, 5, 2, 0.7),
            ("PLANNING",       "SOURCING",       0.6, 0.3, 7, 1, 0.85),
            ("ANALYTICS",      "PLANNING",       0.4, 0.5, 4, 2, 0.65),
            ("QUALITY_CHECK",  "RETURNS",        0.3, 0.4, 3, 3, 0.5),
            ("INVENTORY",      "ANALYTICS",      0.4, 0.3, 5, 2, 0.7),
            ("DELIVERY",       "ANALYTICS",      0.3, 0.5, 4, 2, 0.65),
        ],
    },
    {
        "label": "HEALTH",
        "nodes": ["TRIAGE", "DIAGNOSIS", "TREATMENT_PLAN", "MEDICATION",
                  "PROCEDURE", "MONITORING_H", "RECOVERY", "DISCHARGE",
                  "FOLLOWUP", "INTAKE"],
        "start": "INTAKE", "goal": "DISCHARGE",
        "edges": [
            ("TRIAGE",          "DIAGNOSIS",       0.6, 0.3, 8, 1, 0.9),
            ("DIAGNOSIS",       "TREATMENT_PLAN",  0.5, 0.4, 6, 2, 0.8),
            ("TREATMENT_PLAN",  "MEDICATION",      0.4, 0.3, 7, 2, 0.8),
            ("TREATMENT_PLAN",  "PROCEDURE",       0.6, 0.5, 5, 3, 0.7),
            ("MEDICATION",      "MONITORING_H",    0.3, 0.4, 6, 2, 0.75),
            ("PROCEDURE",       "MONITORING_H",    0.4, 0.3, 5, 3, 0.65),
            ("MONITORING_H",    "RECOVERY",        0.5, 0.3, 7, 1, 0.85),
            ("RECOVERY",        "DISCHARGE",       0.7, 0.2, 9, 0, 0.95),
            ("DISCHARGE",       "FOLLOWUP",        0.3, 0.5, 4, 2, 0.65),
            ("FOLLOWUP",        "DIAGNOSIS",       0.4, 0.6, 3, 3, 0.5),
            ("INTAKE",          "TRIAGE",          0.6, 0.3, 7, 1, 0.85),
            ("MONITORING_H",    "TREATMENT_PLAN",  0.3, 0.5, 3, 4, 0.5),
            ("MEDICATION",      "PROCEDURE",       0.4, 0.4, 4, 3, 0.6),
        ],
    },
    {
        "label": "MUSIC",
        "nodes": ["COMPOSITION", "ARRANGEMENT", "RECORDING", "MIXING",
                  "MASTERING", "RELEASE", "PROMOTION", "PERFORMANCE",
                  "FEEDBACK_M", "INSPIRATION"],
        "start": "INSPIRATION", "goal": "RELEASE",
        "edges": [
            ("COMPOSITION",   "ARRANGEMENT",   0.5, 0.4, 6, 2, 0.75),
            ("ARRANGEMENT",   "RECORDING",     0.6, 0.3, 7, 2, 0.8),
            ("RECORDING",     "MIXING",        0.5, 0.4, 6, 3, 0.7),
            ("MIXING",        "MASTERING",     0.4, 0.3, 7, 1, 0.85),
            ("MASTERING",     "RELEASE",       0.7, 0.2, 9, 0, 0.95),
            ("RELEASE",       "PROMOTION",     0.5, 0.4, 5, 2, 0.7),
            ("PROMOTION",     "PERFORMANCE",   0.4, 0.5, 4, 3, 0.6),
            ("PERFORMANCE",   "FEEDBACK_M",    0.3, 0.4, 5, 2, 0.7),
            ("FEEDBACK_M",    "COMPOSITION",   0.5, 0.6, 3, 3, 0.5),
            ("INSPIRATION",   "COMPOSITION",   0.6, 0.3, 7, 1, 0.85),
            ("RECORDING",     "ARRANGEMENT",   0.3, 0.7, 2, 4, 0.4),
            ("MIXING",        "RECORDING",     0.3, 0.5, 3, 3, 0.5),
            ("PERFORMANCE",   "INSPIRATION",   0.4, 0.4, 4, 2, 0.65),
        ],
    },
    {
        "label": "LEGAL",
        "nodes": ["CONSULTATION", "RESEARCH_L", "DRAFTING", "REVIEW_L",
                  "FILING", "HEARING", "VERDICT", "APPEAL",
                  "COMPLIANCE", "CASE_INTAKE"],
        "start": "CASE_INTAKE", "goal": "VERDICT",
        "edges": [
            ("CONSULTATION",  "RESEARCH_L",  0.5, 0.4, 6, 2, 0.75),
            ("RESEARCH_L",    "DRAFTING",    0.6, 0.5, 5, 3, 0.7),
            ("DRAFTING",      "REVIEW_L",    0.4, 0.3, 7, 2, 0.8),
            ("REVIEW_L",      "FILING",      0.5, 0.3, 7, 1, 0.85),
            ("FILING",        "HEARING",     0.6, 0.4, 6, 2, 0.75),
            ("HEARING",       "VERDICT",     0.7, 0.2, 9, 0, 0.95),
            ("VERDICT",       "APPEAL",      0.4, 0.6, 3, 4, 0.5),
            ("APPEAL",        "HEARING",     0.5, 0.5, 4, 3, 0.6),
            ("COMPLIANCE",    "CONSULTATION", 0.3, 0.4, 5, 2, 0.7),
            ("CASE_INTAKE",   "CONSULTATION", 0.6, 0.3, 7, 1, 0.85),
            ("REVIEW_L",      "DRAFTING",    0.3, 0.6, 2, 3, 0.5),
            ("VERDICT",       "COMPLIANCE",  0.4, 0.3, 6, 1, 0.8),
        ],
    },
    {
        "label": "AGRI",
        "nodes": ["SOIL_PREP", "PLANTING", "IRRIGATION", "FERTILIZING",
                  "PEST_CONTROL", "GROWTH_MONITOR", "HARVEST", "PROCESSING",
                  "MARKET", "SEASON_PLAN"],
        "start": "SEASON_PLAN", "goal": "MARKET",
        "edges": [
            ("SOIL_PREP",       "PLANTING",        0.6, 0.3, 8, 1, 0.9),
            ("PLANTING",        "IRRIGATION",      0.5, 0.4, 6, 2, 0.75),
            ("IRRIGATION",      "FERTILIZING",     0.4, 0.3, 7, 2, 0.8),
            ("FERTILIZING",     "PEST_CONTROL",    0.4, 0.5, 5, 3, 0.65),
            ("PEST_CONTROL",    "GROWTH_MONITOR",  0.3, 0.3, 6, 2, 0.75),
            ("GROWTH_MONITOR",  "HARVEST",         0.6, 0.3, 7, 1, 0.85),
            ("HARVEST",         "PROCESSING",      0.5, 0.4, 6, 2, 0.75),
            ("PROCESSING",      "MARKET",          0.7, 0.2, 9, 0, 0.95),
            ("MARKET",          "SEASON_PLAN",     0.3, 0.5, 4, 2, 0.65),
            ("SEASON_PLAN",     "SOIL_PREP",       0.6, 0.3, 7, 1, 0.85),
            ("GROWTH_MONITOR",  "IRRIGATION",      0.3, 0.5, 3, 3, 0.5),
            ("GROWTH_MONITOR",  "FERTILIZING",     0.3, 0.4, 4, 3, 0.55),
            ("PEST_CONTROL",    "IRRIGATION",      0.3, 0.6, 2, 4, 0.4),
        ],
    },
    {
        "label": "MEDIA",
        "nodes": ["CONCEPT", "SCRIPTING", "PRE_PRODUCTION", "FILMING",
                  "EDITING", "VFX", "SOUND_DESIGN", "DISTRIBUTION",
                  "MARKETING", "PITCH"],
        "start": "PITCH", "goal": "DISTRIBUTION",
        "edges": [
            ("CONCEPT",        "SCRIPTING",        0.5, 0.4, 6, 2, 0.75),
            ("SCRIPTING",      "PRE_PRODUCTION",   0.6, 0.3, 7, 2, 0.8),
            ("PRE_PRODUCTION", "FILMING",          0.7, 0.4, 6, 3, 0.7),
            ("FILMING",        "EDITING",          0.5, 0.3, 7, 2, 0.8),
            ("EDITING",        "VFX",              0.4, 0.5, 5, 3, 0.65),
            ("EDITING",        "SOUND_DESIGN",     0.4, 0.4, 6, 2, 0.75),
            ("VFX",            "SOUND_DESIGN",     0.3, 0.3, 5, 2, 0.7),
            ("SOUND_DESIGN",   "DISTRIBUTION",     0.7, 0.2, 9, 0, 0.95),
            ("DISTRIBUTION",   "MARKETING",        0.5, 0.4, 5, 2, 0.7),
            ("MARKETING",      "PITCH",            0.3, 0.5, 3, 3, 0.5),
            ("PITCH",          "CONCEPT",          0.6, 0.3, 7, 1, 0.85),
            ("FILMING",        "PRE_PRODUCTION",   0.3, 0.7, 2, 4, 0.4),
            ("VFX",            "EDITING",          0.3, 0.5, 3, 3, 0.5),
        ],
    },
    {
        "label": "EDU",
        "nodes": ["CURRICULUM_DESIGN", "MATERIAL_PREP", "LECTURE", "EXERCISE",
                  "ASSESSMENT", "GRADING", "FEEDBACK_E", "REVISION",
                  "GRADUATION", "ENROLLMENT"],
        "start": "ENROLLMENT", "goal": "GRADUATION",
        "edges": [
            ("CURRICULUM_DESIGN", "MATERIAL_PREP",  0.6, 0.3, 7, 2, 0.8),
            ("MATERIAL_PREP",     "LECTURE",         0.5, 0.4, 6, 2, 0.75),
            ("LECTURE",           "EXERCISE",        0.4, 0.3, 7, 1, 0.85),
            ("EXERCISE",         "ASSESSMENT",       0.5, 0.4, 5, 3, 0.7),
            ("ASSESSMENT",       "GRADING",          0.4, 0.3, 6, 2, 0.8),
            ("GRADING",          "FEEDBACK_E",       0.3, 0.4, 5, 2, 0.7),
            ("FEEDBACK_E",       "REVISION",         0.4, 0.5, 4, 3, 0.6),
            ("REVISION",         "LECTURE",          0.3, 0.6, 3, 3, 0.5),
            ("GRADING",          "GRADUATION",       0.7, 0.2, 9, 0, 0.95),
            ("ENROLLMENT",       "CURRICULUM_DESIGN", 0.6, 0.3, 7, 1, 0.85),
            ("ASSESSMENT",       "EXERCISE",         0.3, 0.7, 2, 4, 0.4),
            ("FEEDBACK_E",       "CURRICULUM_DESIGN", 0.3, 0.5, 3, 2, 0.6),
            ("EXERCISE",         "LECTURE",          0.3, 0.5, 3, 3, 0.5),
        ],
    },
    {
        "label": "MAINT",
        "nodes": ["INSPECTION", "FAULT_DETECT", "DIAGNOSIS_M", "PARTS_ORDER",
                  "REPAIR", "CALIBRATION", "TESTING_M", "CERTIFICATION",
                  "SCHEDULING", "ASSET_REGISTER"],
        "start": "ASSET_REGISTER", "goal": "CERTIFICATION",
        "edges": [
            ("INSPECTION",    "FAULT_DETECT",   0.5, 0.3, 7, 2, 0.8),
            ("FAULT_DETECT",  "DIAGNOSIS_M",    0.4, 0.4, 6, 2, 0.75),
            ("DIAGNOSIS_M",   "PARTS_ORDER",    0.5, 0.5, 5, 3, 0.65),
            ("PARTS_ORDER",   "REPAIR",         0.6, 0.3, 7, 2, 0.8),
            ("REPAIR",        "CALIBRATION",    0.4, 0.3, 6, 2, 0.75),
            ("CALIBRATION",   "TESTING_M",      0.5, 0.4, 6, 2, 0.75),
            ("TESTING_M",     "CERTIFICATION",  0.7, 0.2, 9, 0, 0.95),
            ("CERTIFICATION", "SCHEDULING",     0.3, 0.5, 4, 2, 0.65),
            ("SCHEDULING",    "INSPECTION",     0.4, 0.4, 5, 2, 0.7),
            ("ASSET_REGISTER","INSPECTION",     0.6, 0.3, 7, 1, 0.85),
            ("TESTING_M",     "REPAIR",         0.3, 0.6, 2, 4, 0.4),
            ("FAULT_DETECT",  "REPAIR",         0.4, 0.5, 3, 3, 0.5),
            ("DIAGNOSIS_M",   "REPAIR",         0.5, 0.4, 4, 3, 0.6),
        ],
    },
    {
        "label": "LOGIS",
        "nodes": ["ORDER_RECV", "PICK", "PACK", "LABEL",
                  "ROUTE_PLAN", "LOAD", "TRANSIT", "LAST_MILE",
                  "CONFIRM", "DISPATCH_CENTER"],
        "start": "DISPATCH_CENTER", "goal": "CONFIRM",
        "edges": [
            ("ORDER_RECV",      "PICK",           0.5, 0.3, 7, 2, 0.8),
            ("PICK",            "PACK",           0.4, 0.3, 8, 1, 0.9),
            ("PACK",            "LABEL",          0.3, 0.3, 7, 1, 0.85),
            ("LABEL",           "ROUTE_PLAN",     0.5, 0.4, 6, 2, 0.75),
            ("ROUTE_PLAN",      "LOAD",           0.4, 0.3, 7, 1, 0.85),
            ("LOAD",            "TRANSIT",        0.6, 0.3, 8, 1, 0.9),
            ("TRANSIT",         "LAST_MILE",      0.5, 0.4, 6, 2, 0.75),
            ("LAST_MILE",       "CONFIRM",        0.7, 0.2, 9, 0, 0.95),
            ("CONFIRM",         "DISPATCH_CENTER", 0.3, 0.5, 4, 2, 0.65),
            ("DISPATCH_CENTER", "ORDER_RECV",     0.6, 0.3, 7, 1, 0.85),
            ("TRANSIT",         "ROUTE_PLAN",     0.3, 0.6, 2, 4, 0.4),
            ("PACK",            "PICK",           0.3, 0.5, 3, 3, 0.5),
            ("LABEL",           "PACK",           0.3, 0.6, 2, 3, 0.45),
        ],
    },
    {
        "label": "RETAIL",
        "nodes": ["MERCH_PLAN", "BUYING", "RECEIVE", "STOCK",
                  "DISPLAY", "SELL", "CHECKOUT", "CUSTOMER_SVC",
                  "REORDER", "STORE_OPEN"],
        "start": "STORE_OPEN", "goal": "CHECKOUT",
        "edges": [
            ("MERCH_PLAN",    "BUYING",        0.6, 0.4, 6, 2, 0.75),
            ("BUYING",        "RECEIVE",       0.5, 0.3, 7, 2, 0.8),
            ("RECEIVE",       "STOCK",         0.4, 0.3, 8, 1, 0.9),
            ("STOCK",         "DISPLAY",       0.5, 0.4, 6, 2, 0.75),
            ("DISPLAY",       "SELL",          0.6, 0.3, 7, 1, 0.85),
            ("SELL",          "CHECKOUT",      0.7, 0.2, 9, 0, 0.95),
            ("CHECKOUT",      "CUSTOMER_SVC",  0.3, 0.5, 4, 3, 0.6),
            ("CUSTOMER_SVC",  "REORDER",       0.4, 0.4, 5, 2, 0.7),
            ("REORDER",       "BUYING",        0.5, 0.5, 4, 3, 0.6),
            ("STORE_OPEN",    "MERCH_PLAN",    0.6, 0.3, 7, 1, 0.85),
            ("SELL",          "DISPLAY",       0.3, 0.6, 2, 4, 0.4),
            ("STOCK",         "RECEIVE",       0.3, 0.5, 3, 3, 0.5),
            ("CUSTOMER_SVC",  "SELL",          0.4, 0.4, 4, 2, 0.65),
        ],
    },
    {
        "label": "FINTECH",
        "nodes": ["KYC", "ACCOUNT_OPEN", "DEPOSIT", "RISK_ASSESS",
                  "TRANSACTION", "SETTLEMENT", "AUDIT_F", "REPORTING",
                  "COMPLIANCE_F", "ONBOARDING"],
        "start": "ONBOARDING", "goal": "SETTLEMENT",
        "edges": [
            ("KYC",           "ACCOUNT_OPEN",  0.5, 0.3, 8, 1, 0.9),
            ("ACCOUNT_OPEN",  "DEPOSIT",       0.4, 0.3, 7, 2, 0.8),
            ("DEPOSIT",       "RISK_ASSESS",   0.5, 0.4, 6, 2, 0.75),
            ("RISK_ASSESS",   "TRANSACTION",   0.6, 0.4, 6, 3, 0.7),
            ("TRANSACTION",   "SETTLEMENT",    0.7, 0.2, 9, 0, 0.95),
            ("SETTLEMENT",    "AUDIT_F",       0.3, 0.5, 4, 2, 0.65),
            ("AUDIT_F",       "REPORTING",     0.4, 0.3, 6, 2, 0.75),
            ("REPORTING",     "COMPLIANCE_F",  0.3, 0.4, 5, 2, 0.7),
            ("COMPLIANCE_F",  "KYC",           0.4, 0.5, 4, 3, 0.6),
            ("ONBOARDING",    "KYC",           0.6, 0.3, 7, 1, 0.85),
            ("RISK_ASSESS",   "DEPOSIT",       0.3, 0.6, 2, 4, 0.4),
            ("TRANSACTION",   "RISK_ASSESS",   0.3, 0.5, 3, 3, 0.5),
            ("AUDIT_F",       "TRANSACTION",   0.3, 0.6, 2, 3, 0.45),
        ],
    },
    {
        "label": "RESEARCH",
        "nodes": ["LIT_REVIEW", "HYPOTHESIS", "EXPERIMENT_DESIGN", "DATA_COLLECT",
                  "ANALYSIS", "INTERPRETATION", "PEER_REVIEW", "PUBLICATION",
                  "GRANT_WRITE", "QUESTION"],
        "start": "QUESTION", "goal": "PUBLICATION",
        "edges": [
            ("LIT_REVIEW",         "HYPOTHESIS",        0.5, 0.4, 6, 2, 0.75),
            ("HYPOTHESIS",         "EXPERIMENT_DESIGN", 0.6, 0.3, 7, 2, 0.8),
            ("EXPERIMENT_DESIGN",  "DATA_COLLECT",      0.5, 0.5, 5, 3, 0.65),
            ("DATA_COLLECT",       "ANALYSIS",          0.6, 0.3, 7, 2, 0.8),
            ("ANALYSIS",           "INTERPRETATION",    0.4, 0.4, 6, 2, 0.75),
            ("INTERPRETATION",     "PEER_REVIEW",       0.5, 0.3, 7, 1, 0.85),
            ("PEER_REVIEW",        "PUBLICATION",       0.7, 0.2, 9, 0, 0.95),
            ("PEER_REVIEW",        "EXPERIMENT_DESIGN", 0.4, 0.6, 3, 4, 0.5),
            ("PUBLICATION",        "GRANT_WRITE",       0.3, 0.5, 4, 2, 0.65),
            ("QUESTION",           "LIT_REVIEW",        0.6, 0.3, 7, 1, 0.85),
            ("GRANT_WRITE",        "QUESTION",          0.4, 0.4, 5, 2, 0.7),
            ("ANALYSIS",           "DATA_COLLECT",      0.3, 0.6, 2, 4, 0.4),
            ("INTERPRETATION",     "ANALYSIS",          0.3, 0.5, 3, 3, 0.5),
        ],
    },
    {
        "label": "GAME",
        "nodes": ["GAME_DESIGN", "PROTOTYPING", "ART_ASSET", "PROGRAMMING",
                  "LEVEL_DESIGN", "PLAYTESTING", "BALANCING", "QA",
                  "LAUNCH", "PITCH_G"],
        "start": "PITCH_G", "goal": "LAUNCH",
        "edges": [
            ("GAME_DESIGN",  "PROTOTYPING",   0.5, 0.4, 6, 2, 0.75),
            ("PROTOTYPING",  "ART_ASSET",     0.4, 0.5, 5, 3, 0.65),
            ("PROTOTYPING",  "PROGRAMMING",   0.6, 0.4, 6, 3, 0.7),
            ("ART_ASSET",    "LEVEL_DESIGN",  0.5, 0.3, 7, 2, 0.8),
            ("PROGRAMMING",  "LEVEL_DESIGN",  0.5, 0.4, 6, 2, 0.75),
            ("LEVEL_DESIGN", "PLAYTESTING",   0.4, 0.3, 7, 1, 0.85),
            ("PLAYTESTING",  "BALANCING",     0.5, 0.5, 4, 3, 0.6),
            ("BALANCING",    "QA",            0.4, 0.3, 7, 2, 0.8),
            ("QA",           "LAUNCH",        0.7, 0.2, 9, 0, 0.95),
            ("PITCH_G",      "GAME_DESIGN",   0.6, 0.3, 7, 1, 0.85),
            ("PLAYTESTING",  "PROTOTYPING",   0.3, 0.6, 2, 4, 0.4),
            ("QA",           "BALANCING",     0.3, 0.5, 3, 3, 0.5),
            ("BALANCING",    "LEVEL_DESIGN",  0.3, 0.5, 3, 3, 0.5),
        ],
    },
]


def build_bootstrap_landscape(template: dict):
    """Build a bootstrap landscape from a domain template."""
    spec = {
        "nodes": template["nodes"],
        "edges": [
            {
                "from": e[0], "to": e[1],
                "delta": e[2], "resistance": e[3],
                "initial_U": e[4], "initial_F": e[5],
                "confidence": e[6],
            }
            for e in template["edges"]
        ],
    }
    return bootstrap_landscape(spec)


def get_bootstrap_domains(n_needed: int) -> List[dict]:
    """Return the first n_needed bootstrap domain templates."""
    return DOMAIN_TEMPLATES[:n_needed]


# ── Data Structures ──────────────────────────────────────────────────

@dataclass
class QualityMetrics:
    """Quality metrics for a single N-value run."""
    n: int
    n_canon: int
    n_bootstrap: int
    n_pairs: int
    canon_cluster: bool             # EN↔DE cluster formed
    bridge_count: int               # bootstrap domains bridged by ONTO
    de_isolation: bool              # DE isolated from all bootstrap
    bootstrap_compat_pairs: int     # compatible pairs within bootstrap family
    mean_eq_per_pair: float         # avg equivalences per compatible pair
    max_eq_per_pair: float          # max equivalences for any pair
    false_positives: int            # spurious eqs between known-incompatible
    compat_separation: float        # gap: min(incompatible) - max(compatible)
    time_per_episode: float         # avg seconds per episode
    total_time: float               # total run time
    compatible_pairs: List[str]     # which pairs are compatible
    incompatible_pairs: List[str]   # which pairs are incompatible
    all_eq_counts: Dict[str, int]   # final episode equivalence counts


@dataclass
class SaturationReport:
    """Aggregated results across all N values."""
    metrics: List[QualityMetrics]
    collapse_n: Optional[int] = None        # N at which collapse detected
    collapse_reasons: List[str] = field(default_factory=list)


# ── Core Phases ──────────────────────────────────────────────────────

_canon_cache: Dict[str, dict] = {}


def prepare_canon_domains() -> Dict[str, dict]:
    """Train canon domains once, cache for reuse across N values."""
    global _canon_cache
    if _canon_cache:
        return _canon_cache

    print("── Canon Domain Training (cached across runs) ──────────")
    for label, canon_name, start, goal in CANON_DOMAINS:
        t0 = time.time()
        runner = CurriculumRunner(
            canon_name, EXEC_FN,
            equilibrium_threshold=2.0,
            equilibrium_patience=3,
            max_episodes_per_turn=15,
            max_cycles_per_episode=40,
        )
        turn_results = runner.run()
        L = runner.final_landscape
        dt = time.time() - t0
        T_s = structural_temperature(L.historization)
        dp = dream_pressure(L.historization)
        total_steps = sum(r.total_steps for r in turn_results)

        print(f"  {label:6s}: {len(turn_results)} turns, {total_steps:4d} steps, "
              f"T_s={T_s:.3f}, dp={dp:.3f}  ({dt:.1f}s)")
        _canon_cache[label] = {
            "landscape": L, "start": start, "goal": goal,
            "source": "curriculum",
        }
    print()
    return _canon_cache


def run_single_n(n: int) -> QualityMetrics:
    """Run a complete mesh experiment for a given N."""
    print(f"\n{'=' * 70}")
    print(f"  N = {n}  ({3} canon + {n - 3} bootstrapped)")
    print(f"{'=' * 70}")

    t_total_start = time.time()

    # ── Phase 1: Domain preparation ──────────────────────────
    canon = prepare_canon_domains()
    trained = dict(canon)  # shallow copy — Landscapes are shared

    n_bootstrap = n - 3
    if n_bootstrap > 0:
        templates = get_bootstrap_domains(n_bootstrap)
        for tmpl in templates:
            label = tmpl["label"]
            L = build_bootstrap_landscape(tmpl)
            trained[label] = {
                "landscape": L, "start": tmpl["start"],
                "goal": tmpl["goal"], "source": "bootstrap",
            }
            print(f"  {label:6s}: bootstrap, {len(L.states)}n/{len(L.edges)}e")

    all_labels = list(trained.keys())
    n_pairs = len(list(combinations(all_labels, 2)))
    print(f"  → {len(all_labels)} domains, {n_pairs} pairs\n")

    # ── Phase 2: Pre-nav compatibility ───────────────────────
    pre_scores = {}
    for a, b in combinations(all_labels, 2):
        score = dream_compatibility(
            trained[a]["landscape"], trained[b]["landscape"])
        pre_scores[f"{a}↔{b}"] = score

    compatible_pre = [k for k, v in pre_scores.items()
                      if v < COMPATIBILITY_THRESHOLD]
    incompatible_pre = [k for k, v in pre_scores.items()
                        if v >= COMPATIBILITY_THRESHOLD]
    print(f"  Pre-nav: {len(compatible_pre)} compatible, "
          f"{len(incompatible_pre)} incompatible")

    # ── Phase 3: Mesh assembly ───────────────────────────────
    observer = DreamObserver(
        readiness_threshold=0.0,
        node_equivalence_method="hungarian",
        compatibility_threshold=COMPATIBILITY_THRESHOLD,
    )
    controllers = {}
    universes = []
    for label in all_labels:
        info = trained[label]
        L = info["landscape"]
        observer.register(label, L)
        ctrl = E0Controller(L, EXEC_FN, hybrid_mode=HybridMode.GREEDY)
        controllers[label] = ctrl
        universes.append(Universe(
            name=label, landscape=L,
            execute_fn=EXEC_FN, start=info["start"], goal=info["goal"],
        ))
    router = CouplingRouter(universes)

    # ── Phase 4: Episodes ────────────────────────────────────
    episode_times = []
    final_eq_counts = {}

    for ep in range(1, N_EPISODES + 1):
        t_ep_start = time.time()

        # Wake
        for label in all_labels:
            info = trained[label]
            ctrl = controllers[label]
            ctrl.run(info["start"], max_cycles=MAX_CYCLES_PER_RUN,
                     goal=info["goal"])

        # Sleep
        dream_result = observer.dream_cycle()
        update_weights_from_dream(router, observer)

        # Collect
        eq_counts = {}
        for a, b in combinations(all_labels, 2):
            eqs_a = observer.equivalences_for(a)
            count = sum(1 for eq in eqs_a
                        if eq["partner_state"].startswith(f"{b}:"))
            eq_counts[f"{a}↔{b}"] = count

        final_eq_counts = eq_counts
        t_ep = time.time() - t_ep_start
        episode_times.append(t_ep)

        active = {k: v for k, v in eq_counts.items() if v > 0}
        print(f"  Ep {ep:2d}: {len(active)} active pairs, "
              f"Σeq={sum(active.values())}, {t_ep:.1f}s")

    # ── Phase 5: Post-nav compatibility ──────────────────────
    post_scores = {}
    for a, b in combinations(all_labels, 2):
        score = dream_compatibility(
            trained[a]["landscape"], trained[b]["landscape"])
        post_scores[f"{a}↔{b}"] = score

    compatible_post = [k for k, v in post_scores.items()
                       if v < COMPATIBILITY_THRESHOLD]
    incompatible_post = [k for k, v in post_scores.items()
                         if v >= COMPATIBILITY_THRESHOLD]

    # ── Phase 6: Quality measurement ─────────────────────────

    # 1. EN↔DE cluster
    en_de_eq = final_eq_counts.get("EN↔DE", 0)
    canon_cluster = en_de_eq > 0

    # 2. ONTO bridge count
    bootstrap_labels = [l for l in all_labels if l not in ("EN", "DE", "ONTO")]
    bridge_count = 0
    for bl in bootstrap_labels:
        key = f"ONTO↔{bl}"
        if final_eq_counts.get(key, 0) > 0:
            bridge_count += 1

    # 3. DE isolation
    de_cross_eq = 0
    for bl in bootstrap_labels:
        de_cross_eq += final_eq_counts.get(f"DE↔{bl}", 0)
    de_isolation = de_cross_eq == 0

    # 4. Bootstrap internal pairs
    bootstrap_pairs = 0
    for a, b in combinations(bootstrap_labels, 2):
        key = f"{a}↔{b}"
        if post_scores.get(key, 1.0) < COMPATIBILITY_THRESHOLD:
            bootstrap_pairs += 1

    # 5. Mean equivalences per compatible pair
    compat_eq_values = []
    for pair in compatible_post:
        compat_eq_values.append(final_eq_counts.get(pair, 0))
    mean_eq = (sum(compat_eq_values) / len(compat_eq_values)
               if compat_eq_values else 0.0)
    max_eq = max(compat_eq_values) if compat_eq_values else 0.0

    # 6. False positives: equivalences between known-incompatible pairs
    false_pos = 0
    for pair in incompatible_post:
        if final_eq_counts.get(pair, 0) > 0:
            false_pos += 1

    # 7. Compatibility separation
    if incompatible_post and compatible_post:
        min_incompat = min(post_scores[p] for p in incompatible_post)
        max_compat = max(post_scores[p] for p in compatible_post)
        compat_sep = min_incompat - max_compat
    else:
        compat_sep = float("inf")

    t_total = time.time() - t_total_start

    metrics = QualityMetrics(
        n=n,
        n_canon=3,
        n_bootstrap=n_bootstrap,
        n_pairs=n_pairs,
        canon_cluster=canon_cluster,
        bridge_count=bridge_count,
        de_isolation=de_isolation,
        bootstrap_compat_pairs=bootstrap_pairs,
        mean_eq_per_pair=mean_eq,
        max_eq_per_pair=max_eq,
        false_positives=false_pos,
        compat_separation=compat_sep,
        time_per_episode=sum(episode_times) / len(episode_times),
        total_time=t_total,
        compatible_pairs=compatible_post,
        incompatible_pairs=incompatible_post,
        all_eq_counts=final_eq_counts,
    )

    # Print summary
    print(f"\n  Quality Summary for N={n}:")
    print(f"    EN↔DE cluster:      {'YES' if canon_cluster else 'NO'} "
          f"(eq={en_de_eq})")
    print(f"    ONTO bridge count:  {bridge_count} / {len(bootstrap_labels)}")
    print(f"    DE isolation:       {'YES' if de_isolation else 'NO'} "
          f"(cross-eq={de_cross_eq})")
    print(f"    Bootstrap pairs:    {bootstrap_pairs}")
    print(f"    Mean eq/compat:     {mean_eq:.1f}")
    print(f"    Max eq/pair:        {max_eq:.0f}")
    print(f"    False positives:    {false_pos}")
    print(f"    Compat separation:  {compat_sep:.4f}")
    print(f"    Time/episode:       {metrics.time_per_episode:.1f}s")
    print(f"    Total time:         {t_total:.1f}s")

    return metrics


def analyze_saturation(all_metrics: List[QualityMetrics]) -> SaturationReport:
    """Find the collapse point across N values."""
    report = SaturationReport(metrics=all_metrics)

    # Baseline: N=5 metrics (or smallest N with bootstrap)
    baseline = None
    for m in all_metrics:
        if m.n >= 5:
            baseline = m
            break

    if baseline is None:
        return report

    reasons = []

    for m in all_metrics:
        if m.n <= 5:
            continue  # skip baseline and below

        # Check collapse indicators
        if not m.canon_cluster:
            reasons.append(f"N={m.n}: EN↔DE cluster lost")
        if m.bridge_count == 0 and m.n_bootstrap > 0:
            reasons.append(f"N={m.n}: ONTO bridge dropped to 0")
        if not m.de_isolation:
            reasons.append(f"N={m.n}: DE gained spurious connections")
        if m.false_positives > 0:
            reasons.append(f"N={m.n}: {m.false_positives} false positive pairs")
        if baseline.mean_eq_per_pair > 0:
            ratio = m.mean_eq_per_pair / baseline.mean_eq_per_pair
            if ratio < 0.50:
                reasons.append(
                    f"N={m.n}: mean eq/pair dropped to {ratio:.0%} of baseline")
        if m.compat_separation < 0.05:
            reasons.append(
                f"N={m.n}: compat separation too narrow ({m.compat_separation:.4f})")

    report.collapse_reasons = reasons

    # Collapse N: first N with any collapse indicator
    for m in sorted(all_metrics, key=lambda x: x.n):
        if m.n <= 5:
            continue
        collapse_for_n = [r for r in reasons if r.startswith(f"N={m.n}:")]
        if collapse_for_n:
            report.collapse_n = m.n
            break

    return report


# ── Main ─────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("C182 — Mesh Saturation Point Exploration")
    print(f"Test sizes: {TEST_SIZES}")
    print("=" * 70)
    print()

    all_metrics = []
    for n in TEST_SIZES:
        metrics = run_single_n(n)
        all_metrics.append(metrics)

    # ── Saturation Analysis ──────────────────────────────────
    report = analyze_saturation(all_metrics)

    print("\n" + "=" * 70)
    print("  SATURATION ANALYSIS")
    print("=" * 70)

    # Summary table
    print(f"\n  {'N':>3s}  {'Pairs':>5s}  {'EN↔DE':>5s}  {'Bridge':>6s}  "
          f"{'DE iso':>6s}  {'BPairs':>6s}  {'MeanEq':>7s}  {'FP':>3s}  "
          f"{'CompatΔ':>8s}  {'T/ep':>5s}")
    print(f"  {'─' * 3}  {'─' * 5}  {'─' * 5}  {'─' * 6}  {'─' * 6}  "
          f"{'─' * 6}  {'─' * 7}  {'─' * 3}  {'─' * 8}  {'─' * 5}")
    for m in all_metrics:
        en_de = "YES" if m.canon_cluster else "NO"
        de = "YES" if m.de_isolation else "NO"
        print(f"  {m.n:3d}  {m.n_pairs:5d}  {en_de:>5s}  {m.bridge_count:6d}  "
              f"{de:>6s}  {m.bootstrap_compat_pairs:6d}  {m.mean_eq_per_pair:7.1f}  "
              f"{m.false_positives:3d}  {m.compat_separation:8.4f}  "
              f"{m.time_per_episode:5.1f}s")

    # Time scaling
    if len(all_metrics) >= 2:
        print(f"\n  Time scaling:")
        first = all_metrics[0]
        for m in all_metrics:
            if first.time_per_episode > 0:
                ratio = m.time_per_episode / first.time_per_episode
            else:
                ratio = 0.0
            pairs = m.n_pairs
            print(f"    N={m.n:2d}: {m.time_per_episode:5.1f}s/ep  "
                  f"(×{ratio:.1f} vs N={first.n}), "
                  f"C({m.n},2)={pairs} pairs")

    # Collapse verdict
    print()
    if report.collapse_n is not None:
        print(f"  ◆ COLLAPSE DETECTED at N = {report.collapse_n}")
        for reason in report.collapse_reasons:
            print(f"    - {reason}")
    else:
        print(f"  ◆ NO COLLAPSE detected up to N = {all_metrics[-1].n}")
        print(f"    All quality metrics remain stable.")

    # Degradation trends (even if no collapse)
    if len(all_metrics) >= 3:
        print(f"\n  Degradation trends:")
        first_bridge = None
        for m in all_metrics:
            if m.n_bootstrap > 0 and first_bridge is None:
                first_bridge = m.bridge_count
            if m.n_bootstrap > 0 and first_bridge and first_bridge > 0:
                bridge_pct = m.bridge_count / m.n_bootstrap * 100
                print(f"    N={m.n:2d}: bridge covers "
                      f"{m.bridge_count}/{m.n_bootstrap} = {bridge_pct:.0f}% "
                      f"of bootstrapped domains")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
