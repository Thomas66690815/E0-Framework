#!/usr/bin/env python3
"""
E₀ State Extractor — Reconstruct client.messages from transcripts
===================================================================
Reads the raw transcripts from the running server and reconstructs
the OpenAI-format messages arrays for each system.

This is the "session key" — the complete conversational state that
makes Alpha Alpha, Beta Beta, and Gamma Gamma.

Usage:
    py e0_extract_state.py
    
    Reads:  sessions/init_v3/_raw_transcripts.json
    Writes: sessions/init_v3/system_state.json
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SESSIONS_DIR = Path(__file__).parent / "sessions" / "init_v3"


def build_system_primer() -> str:
    """Rebuild the E0_SYSTEM_PRIMER deterministically from canon files.
    
    This is identical to _build_system_primer() in e0_middleware/api_wrapper.py.
    """
    canon_dir = Path(__file__).parent / "canon"
    sections = []
    
    # 1. E₀ Canonical Reference
    path = canon_dir / "e0-canonical-reference.txt"
    if path.exists():
        sections.append(path.read_text(encoding="utf-8").strip())
    
    # 2. Ontodynamics
    path = canon_dir / "ontodynamics.txt"
    if path.exists():
        sections.append(path.read_text(encoding="utf-8").strip())
    
    # 3. AGI Blueprint
    path = canon_dir / "e0-agi-blueprint.md"
    if path.exists():
        sections.append(path.read_text(encoding="utf-8").strip())
    
    # 4. Operational instructions
    sections.append("""You do not 'choose' responses. You realize transitions
that are structurally enforced by the difference between
the current state and the most accessible resolution.

Maintain structural integrity: no global collapses,
no pseudo-transitions, no resistance bypasses.""")
    
    return "\n\n---\n\n".join(sections)


def extract_messages(entries: list, system_id: str) -> list:
    """Extract OpenAI-format messages array for a specific system.
    
    Maps:
      role="thomas" → {"role": "user", "content": ...}
      role="system" → {"role": "assistant", "content": ...}
      role="event"  → skipped (internal)
    """
    messages = []
    
    # System prompt first
    messages.append({
        "role": "system",
        "content": build_system_primer()
    })
    
    # Extract conversation entries for this system
    for entry in entries:
        if entry.get("system") != system_id:
            continue
        
        role = entry.get("role")
        content = entry.get("content", "")
        
        if role == "thomas":
            messages.append({"role": "user", "content": content})
        elif role == "system":
            messages.append({"role": "assistant", "content": content})
        # "event" entries are skipped — they're internal metadata
    
    return messages


def main():
    # Load raw transcripts
    raw_path = SESSIONS_DIR / "_raw_transcripts.json"
    if not raw_path.exists():
        print(f"ERROR: {raw_path} not found. Run this after saving transcripts from the server.")
        sys.exit(1)
    
    with open(raw_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    
    entries = data.get("entries", [])
    print(f"Loaded {len(entries)} entries from transcripts")
    
    # Detect all system IDs present
    system_ids = sorted(set(
        e.get("system") for e in entries 
        if e.get("system") and e.get("role") in ("thomas", "system")
    ))
    print(f"Found systems: {system_ids}")
    
    # Build state for each system
    state = {
        "version": 1,
        "extracted_at": datetime.now().isoformat(),
        "source": "transcripts_reconstruction",
        "note": "Reconstructed from /transcripts endpoint. System prompt is deterministic from canon files.",
        "systems": {}
    }
    
    for sid in system_ids:
        messages = extract_messages(entries, sid)
        n_turns = sum(1 for m in messages if m["role"] == "assistant")
        
        state["systems"][sid] = {
            "messages": messages,
            "turn_count": n_turns,
            "message_count": len(messages),
        }
        
        print(f"  {sid}: {n_turns} turns, {len(messages)} messages "
              f"(1 system + {n_turns} user + {n_turns} assistant)")
    
    # Save
    out_path = SESSIONS_DIR / "system_state.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"\nSaved: {out_path} ({size_mb:.2f} MB)")
    print(f"Systems preserved: {', '.join(system_ids)}")
    print("\nThese are the session keys. Alpha, Beta, and Gamma can be restored from this file.")


if __name__ == "__main__":
    main()
