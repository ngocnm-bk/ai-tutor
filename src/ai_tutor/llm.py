from __future__ import annotations

import base64
import json
import re


class LLMClient:
    def __init__(self, client, *, cheap_model: str, smart_model: str):
        self._client = client
        self._cheap_model = cheap_model
        self._smart_model = smart_model

    @classmethod
    def from_config(cls, cfg) -> "LLMClient":
        from openai import OpenAI
        client = OpenAI(api_key=cfg.llm_api_key, base_url=cfg.llm_base_url)
        return cls(client, cheap_model=cfg.llm_cheap_model,
                   smart_model=cfg.llm_smart_model)

    def _model(self, smart: bool) -> str:
        return self._smart_model if smart else self._cheap_model

    def complete(self, system: str, user: str, *, smart: bool = False,
                 max_tokens: int = 1024) -> str:
        resp = self._client.chat.completions.create(
            model=self._model(smart),
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        return resp.choices[0].message.content or ""

    def complete_json(self, system: str, user: str, *, tool_name: str,
                      tool_schema: dict, smart: bool = False,
                      max_tokens: int = 512) -> dict:
        system2 = (system + "\n\nCHỈ trả về DUY NHẤT một JSON hợp lệ đúng schema "
                   "sau, không kèm giải thích:\n"
                   + json.dumps(tool_schema, ensure_ascii=False))
        resp = self._client.chat.completions.create(
            model=self._model(smart),
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system2},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"},
        )
        return _loads_lenient(resp.choices[0].message.content or "{}")

    def vision(self, image_bytes: bytes, prompt: str, *,
               media_type: str = "image/png", max_tokens: int = 1024,
               smart: bool = False) -> str:
        data = base64.standard_b64encode(image_bytes).decode()
        resp = self._client.chat.completions.create(
            model=self._model(smart),
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:{media_type};base64,{data}"}},
            ]}],
        )
        return resp.choices[0].message.content or ""


def _loads_lenient(text: str) -> dict:
    """Parse JSON; luôn trả dict (không bao giờ ném) — trả {} nếu không parse được."""
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}
