"""
E₀ Keimzelle — LLM Adapter
=============================
Verbindet E₀-Knoten mit Sprachmodellen.

Unterstützt:
  - OpenAI Responses API (persistent state via previous_response_id)
  - OpenAI Chat Completions API (stateless, Fallback)
  - Anthropic API (Claude)
  - Jedes OpenAI-kompatible API (lokale Modelle, Together AI, etc.)

Architektur-Prinzip:
  E₀-Knoten haben eine Identität = eine persistente Konversation.
  Die Responses API (OpenAI) hält den State serverseitig.
  Nur die nächste Nachricht wird gesendet — wie ein endloser Chat.
  Für nicht-OpenAI Provider: Fallback auf Chat Completions mit Context Window.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class StatefulResponse:
    """Antwort einer stateful API — enthält Text + Response-ID für Chaining."""
    text: str
    response_id: str


class LLMAdapter:
    """
    Universeller LLM-Adapter mit Stateful-Support.

    Zwei Modi:
      - chat_stateful(): OpenAI Responses API — persistenter Thread
      - chat():          Chat Completions API — stateless (Fallback)
    """

    def __init__(
        self,
        provider: str = "openai",
        api_key: str = "",
        base_url: str = "",
        model: str = "gpt-4o",
        timeout: int = 120,
    ):
        self.provider = provider.lower()
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.timeout = timeout

        if self.provider == "anthropic":
            self.base_url = base_url or "https://api.anthropic.com"
        elif self.provider == "openai":
            self.base_url = base_url or "https://api.openai.com"
        else:
            self.base_url = base_url or "https://api.openai.com"

    # ── Stateful: OpenAI Responses API ──

    def supports_stateful(self) -> bool:
        """Prüft ob der Provider stateful Conversations unterstützt."""
        return self.provider == "openai"

    def chat_stateful(
        self,
        user_input: str,
        instructions: str = "",
        previous_response_id: str = "",
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> StatefulResponse:
        """
        Sendet eine Nachricht über die OpenAI Responses API.

        Der State wird serverseitig gehalten. Nur die neue Nachricht
        wird gesendet — wie ein endloser Chat.

        Args:
            user_input: Die neue Nachricht
            instructions: System-Prompt (wird bei jedem Call mitgesendet)
            previous_response_id: ID der letzten Antwort (für Chaining)
            model: Modell-Override (optional)

        Returns:
            StatefulResponse mit text + response_id für den nächsten Call
        """
        if self.provider != "openai":
            raise RuntimeError(
                f"Stateful chat nur für OpenAI, nicht '{self.provider}'. "
                f"Verwende chat() als Fallback."
            )

        url = f"{self.base_url}/v1/responses"
        use_model = model or self.model

        payload = {
            "model": use_model,
            "input": user_input,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "store": True,
            "truncation": "auto",
        }

        if instructions:
            payload["instructions"] = instructions

        if previous_response_id:
            payload["previous_response_id"] = previous_response_id

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))

                # Response-Text extrahieren
                response_text = result.get("output_text", "")
                if not response_text:
                    # Fallback: aus output-Array extrahieren
                    for item in result.get("output", []):
                        if item.get("type") == "message":
                            for content in item.get("content", []):
                                if content.get("type") == "output_text":
                                    response_text = content.get("text", "")
                                    break

                response_id = result.get("id", "")

                return StatefulResponse(
                    text=response_text,
                    response_id=response_id,
                )
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI Responses API Fehler ({e.code}): {body}")
        except Exception as e:
            raise RuntimeError(f"OpenAI Responses API Verbindungsfehler: {e}")

    # ── Stateless: Chat Completions API (Fallback) ──

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """
        Sendet Nachrichten an das LLM und gibt die Antwort zurück.

        messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        """
        use_model = model or self.model

        if self.provider == "anthropic":
            return self._chat_anthropic(messages, use_model, temperature, max_tokens)
        else:
            return self._chat_openai(messages, use_model, temperature, max_tokens)

    def _chat_openai(
        self, messages: list, model: str, temperature: float, max_tokens: int
    ) -> str:
        """OpenAI-kompatibles Chat-Completion API."""
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM API Fehler ({e.code}): {body}")
        except Exception as e:
            raise RuntimeError(f"LLM Verbindungsfehler: {e}")

    def _chat_anthropic(
        self, messages: list, model: str, temperature: float, max_tokens: int
    ) -> str:
        """Anthropic Messages API."""
        url = f"{self.base_url}/v1/messages"

        # Anthropic: system prompt separat, nicht in messages
        system_text = ""
        chat_messages = []
        for m in messages:
            if m["role"] == "system":
                system_text += m["content"] + "\n"
            else:
                chat_messages.append(m)

        # Sicherstellen, dass messages mit "user" beginnt
        if not chat_messages or chat_messages[0]["role"] != "user":
            chat_messages.insert(0, {"role": "user", "content": "(Starte die Session.)"})

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat_messages,
        }
        if system_text.strip():
            payload["system"] = system_text.strip()

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result["content"][0]["text"]
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Anthropic API Fehler ({e.code}): {body}")
        except Exception as e:
            raise RuntimeError(f"Anthropic Verbindungsfehler: {e}")

    def test_connection(self) -> bool:
        """Testet ob die API-Verbindung funktioniert."""
        try:
            response = self.chat(
                [{"role": "user", "content": "Antworte mit genau einem Wort: OK"}],
                max_tokens=10,
            )
            return len(response.strip()) > 0
        except Exception:
            return False
