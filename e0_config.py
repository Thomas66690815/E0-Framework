"""
E0 Config -- Persistent configuration for E0 Framework
========================================================
Stores user preferences in ~/.e0/config.json so you don't
have to pass --api KEY every single time.

Config file structure:
{
  "api_key": "tgp_v1_...",
  "base_url": "https://api.together.xyz/v1",
  "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
  "lang": "en",
  "port": 3000
}
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

CONFIG_DIR = Path.home() / ".e0"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Models that work well with E0, ordered by recommendation
RECOMMENDED_MODELS = [
    ("meta-llama/Llama-3.3-70B-Instruct-Turbo", "Llama 3.3 70B — best quality, fast via Together AI"),
    ("Qwen/Qwen2.5-72B-Instruct-Turbo", "Qwen 2.5 72B — strong alternative"),
    ("Qwen/Qwen2.5-7B-Instruct-Turbo", "Qwen 2.5 7B — fast, lower cost"),
    ("meta-llama/Llama-3.1-8B-Instruct-Turbo", "Llama 3.1 8B — minimal cost"),
]

DEFAULT_MODEL_API = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
DEFAULT_MODEL_LOCAL = "gpt2"


def load_config() -> Dict[str, Any]:
    """Load config from ~/.e0/config.json. Returns empty dict if not found."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(config: Dict[str, Any]) -> Path:
    """Save config to ~/.e0/config.json. Creates directory if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    return CONFIG_FILE


def has_config() -> bool:
    """Check if a config file exists with at least an API key."""
    cfg = load_config()
    return bool(cfg.get("api_key"))


def detect_base_url(api_key: str, base_url: Optional[str] = None) -> Optional[str]:
    """Auto-detect base URL from API key prefix."""
    if base_url:
        return base_url
    if api_key and api_key.startswith("tgp_"):
        return "https://api.together.xyz/v1"
    return None


def first_run_setup(lang: str = "en") -> Dict[str, Any]:
    """Interactive first-run setup wizard. Returns config dict.
    
    This runs in the terminal before the web UI starts. It asks
    the minimum necessary questions to get E0 working.
    """
    texts = _SETUP_TEXTS[lang]
    
    print()
    print("=" * 60)
    print(texts["welcome"])
    print("=" * 60)
    print()
    print(texts["intro"])
    print()
    
    # Step 1: API key
    print(texts["step1_header"])
    print(texts["step1_info"])
    print()
    api_key = input(texts["step1_prompt"]).strip()
    
    if not api_key:
        # Local mode
        print()
        print(texts["local_mode"])
        config = {
            "model": DEFAULT_MODEL_LOCAL,
            "lang": lang,
            "port": 3000,
        }
        save_config(config)
        print(texts["saved"].format(path=CONFIG_FILE))
        print()
        return config
    
    # Step 2: Base URL (auto-detect)
    base_url = detect_base_url(api_key)
    if base_url:
        provider = "Together AI" if "together" in base_url else base_url
        print(texts["provider_detected"].format(provider=provider))
    else:
        print()
        print(texts["step2_info"])
        base_url = input(texts["step2_prompt"]).strip()
        if not base_url:
            base_url = "https://api.together.xyz/v1"
            print(texts["provider_default"])
    
    # Step 3: Model selection
    print()
    print(texts["step3_header"])
    for idx, (model_id, desc) in enumerate(RECOMMENDED_MODELS, 1):
        marker = " *" if idx == 1 else ""
        print(f"  [{idx}] {desc}{marker}")
    print(f"  [5] " + texts["step3_custom"])
    print()
    choice = input(texts["step3_prompt"]).strip()
    
    if choice == "5":
        model = input(texts["step3_custom_prompt"]).strip()
        if not model:
            model = DEFAULT_MODEL_API
    elif choice in ("1", "2", "3", "4"):
        model = RECOMMENDED_MODELS[int(choice) - 1][0]
    else:
        model = DEFAULT_MODEL_API
        print(texts["model_default"].format(model=model))
    
    # Step 4: Language
    print()
    print(texts["step4_header"])
    print("  [1] English")
    print("  [2] Deutsch")
    lang_choice = input(texts["step4_prompt"]).strip()
    if lang_choice == "2":
        lang = "de"
    else:
        lang = "en"
    
    # Save
    config = {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "lang": lang,
        "port": 3000,
    }
    save_config(config)
    
    print()
    print("=" * 60)
    print(texts["done"])
    print(texts["saved"].format(path=CONFIG_FILE))
    print(texts["edit_hint"])
    print("=" * 60)
    print()
    
    return config


def merge_args_with_config(args) -> Dict[str, Any]:
    """Merge CLI args with saved config. CLI args take priority."""
    config = load_config()
    
    result = {
        "api_key": args.api or config.get("api_key"),
        "base_url": args.base_url or config.get("base_url"),
        "model": args.model or config.get("model"),
        "lang": args.lang if args.lang != "en" or not config.get("lang") else config.get("lang", "en"),
        "port": args.port if args.port != 3000 or not config.get("port") else config.get("port", 3000),
        "device": getattr(args, "device", "cpu"),
        "detail": getattr(args, "detail", False),
        "web": getattr(args, "web", False),
        "profile": getattr(args, "profile", None),
    }
    
    # Auto-detect base URL
    if result["api_key"] and not result["base_url"]:
        result["base_url"] = detect_base_url(result["api_key"])
    
    # Default model based on mode
    if not result["model"]:
        if result["api_key"]:
            result["model"] = DEFAULT_MODEL_API
        else:
            result["model"] = DEFAULT_MODEL_LOCAL
    
    return result


# ── Setup wizard texts ──

_SETUP_TEXTS = {
    "en": {
        "welcome": "  E\u2080 Framework -- First Run Setup",
        "intro": (
            "  This is a one-time setup. It saves your preferences so you\n"
            "  can start E\u2080 with just: py e0_start.py --web"
        ),
        "step1_header": "  Step 1: API Key",
        "step1_info": (
            "  E\u2080 works best with large language models (30B+) via API.\n"
            "  Recommended: Together AI (https://api.together.xyz)\n"
            "  You can also press Enter to use a local model (GPT-2, no key needed)."
        ),
        "step1_prompt": "  API key (or Enter for local mode): ",
        "local_mode": "  \u2192 Local mode selected. Using GPT-2 on CPU.\n  (Limited quality, but works offline with zero cost.)",
        "provider_detected": "  \u2192 Detected: {provider}",
        "provider_default": "  \u2192 Using Together AI as default provider.",
        "step2_info": "  Enter your API provider's base URL.",
        "step2_prompt": "  Base URL (Enter = Together AI): ",
        "step3_header": "  Step 2: Model",
        "step3_custom": "Custom model name",
        "step3_prompt": "  Choose [1-5] (Enter = 1): ",
        "step3_custom_prompt": "  Model name: ",
        "model_default": "  \u2192 Using {model}",
        "step4_header": "  Step 3: Language",
        "step4_prompt": "  Choose [1-2] (Enter = 1): ",
        "done": "  Setup complete!",
        "saved": "  Config saved to: {path}",
        "edit_hint": "  You can edit this file anytime or re-run setup with: py e0_start.py --setup",
    },
    "de": {
        "welcome": "  E\u2080 Framework -- Ersteinrichtung",
        "intro": (
            "  Dies ist eine einmalige Einrichtung. Deine Einstellungen werden\n"
            "  gespeichert, damit du E\u2080 k\u00fcnftig einfach starten kannst: py e0_start.py --web"
        ),
        "step1_header": "  Schritt 1: API-Schl\u00fcssel",
        "step1_info": (
            "  E\u2080 funktioniert am besten mit gro\u00dfen Sprachmodellen (30B+) \u00fcber API.\n"
            "  Empfohlen: Together AI (https://api.together.xyz)\n"
            "  Du kannst auch Enter dr\u00fccken f\u00fcr ein lokales Modell (GPT-2, kein Key n\u00f6tig)."
        ),
        "step1_prompt": "  API-Schl\u00fcssel (oder Enter f\u00fcr lokalen Modus): ",
        "local_mode": "  \u2192 Lokaler Modus gew\u00e4hlt. Verwende GPT-2 auf CPU.\n  (Eingeschr\u00e4nkte Qualit\u00e4t, aber funktioniert offline und kostenlos.)",
        "provider_detected": "  \u2192 Erkannt: {provider}",
        "provider_default": "  \u2192 Verwende Together AI als Standard-Provider.",
        "step2_info": "  Gib die Basis-URL deines API-Providers ein.",
        "step2_prompt": "  Basis-URL (Enter = Together AI): ",
        "step3_header": "  Schritt 2: Modell",
        "step3_custom": "Eigener Modellname",
        "step3_prompt": "  W\u00e4hle [1-5] (Enter = 1): ",
        "step3_custom_prompt": "  Modellname: ",
        "model_default": "  \u2192 Verwende {model}",
        "step4_header": "  Schritt 3: Sprache",
        "step4_prompt": "  W\u00e4hle [1-2] (Enter = 1): ",
        "done": "  Einrichtung abgeschlossen!",
        "saved": "  Konfiguration gespeichert in: {path}",
        "edit_hint": "  Du kannst die Datei jederzeit bearbeiten oder Setup neu starten: py e0_start.py --setup",
    },
}
