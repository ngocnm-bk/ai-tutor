from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    base_url: str | None
    key_env: str
    cheap_model: str
    smart_model: str


PROVIDERS: dict[str, ProviderSpec] = {
    "gemini": ProviderSpec(
        "https://generativelanguage.googleapis.com/v1beta/openai/",
        "GEMINI_API_KEY", "gemini-2.5-flash", "gemini-2.5-pro"),
    "openai": ProviderSpec(
        None, "OPENAI_API_KEY", "gpt-4o-mini", "gpt-4o"),
    "grok": ProviderSpec(
        "https://api.x.ai/v1", "XAI_API_KEY", "grok-3-mini", "grok-3"),
    "claude": ProviderSpec(
        "https://api.anthropic.com/v1/", "ANTHROPIC_API_KEY",
        "claude-haiku-4-5-20251001", "claude-sonnet-4-6"),
}
