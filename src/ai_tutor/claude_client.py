from __future__ import annotations


class ClaudeClient:
    def __init__(self, client, *, cheap_model="claude-haiku-4-5-20251001",
                 smart_model="claude-sonnet-4-6"):
        self._client = client
        self._cheap_model = cheap_model
        self._smart_model = smart_model

    @classmethod
    def from_config(cls, cfg) -> "ClaudeClient":
        import anthropic
        return cls(anthropic.Anthropic(api_key=cfg.anthropic_api_key))

    def complete(self, system: str, user: str, *, smart: bool = False,
                 max_tokens: int = 1024) -> str:
        model = self._smart_model if smart else self._cheap_model
        resp = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
