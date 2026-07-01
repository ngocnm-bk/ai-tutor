import json
from types import SimpleNamespace
from unittest.mock import patch
from ai_tutor.llm import LLMClient


def _resp(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeCompletions:
    def __init__(self, content): self.content = content; self.last = None
    def create(self, **kw): self.last = kw; return _resp(self.content)


class FakeClient:
    def __init__(self, content="xin chào"):
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


def test_complete_uses_cheap_model_and_returns_text():
    fake = FakeClient("xin chào")
    c = LLMClient(fake, cheap_model="cheap", smart_model="smart")
    out = c.complete("s", "u")
    assert out == "xin chào"
    kw = fake.chat.completions.last
    assert kw["model"] == "cheap"
    assert kw["messages"][0]["role"] == "system" and kw["messages"][1]["role"] == "user"


def test_complete_smart_uses_smart_model():
    fake = FakeClient()
    c = LLMClient(fake, cheap_model="cheap", smart_model="smart")
    c.complete("s", "u", smart=True, max_tokens=200)
    assert fake.chat.completions.last["model"] == "smart"
    assert fake.chat.completions.last["max_tokens"] == 200


def test_complete_json_parses_json_mode():
    fake = FakeClient(json.dumps({"lop": 3, "mon": "toan"}))
    c = LLMClient(fake, cheap_model="cheap", smart_model="smart")
    out = c.complete_json("s", "u", tool_name="classify", tool_schema={"type": "object"})
    assert out == {"lop": 3, "mon": "toan"}
    assert fake.chat.completions.last["response_format"] == {"type": "json_object"}


def test_complete_json_lenient_on_extra_text():
    fake = FakeClient('Đây là kết quả: {"lop": 6, "mon": "tieng-anh"} .')
    c = LLMClient(fake, cheap_model="cheap", smart_model="smart")
    assert c.complete_json("s", "u", tool_name="x", tool_schema={})["lop"] == 6


def test_vision_sends_image_url():
    fake = FakeClient("6 x 7 = ?")
    c = LLMClient(fake, cheap_model="cheap", smart_model="smart")
    out = c.vision(b"IMG", "trích text", media_type="image/png")
    assert out == "6 x 7 = ?"
    content = fake.chat.completions.last["messages"][0]["content"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_from_config_builds_openai_client():
    cfg = SimpleNamespace(llm_api_key="k", llm_base_url="http://x",
                          llm_cheap_model="c", llm_smart_model="s")
    with patch("openai.OpenAI") as MockOpenAI:
        MockOpenAI.return_value = SimpleNamespace(chat=None)
        c = LLMClient.from_config(cfg)
    MockOpenAI.assert_called_once_with(api_key="k", base_url="http://x")
    assert isinstance(c, LLMClient)
