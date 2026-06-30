from types import SimpleNamespace
from unittest.mock import patch
from ai_tutor.claude_client import ClaudeClient


class FakeMessages:
    def __init__(self):
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="xin chào")])


class FakeAnthropic:
    def __init__(self):
        self.messages = FakeMessages()


def test_complete_returns_text_and_uses_cheap_model_by_default():
    fake = FakeAnthropic()
    client = ClaudeClient(fake)
    out = client.complete(system="s", user="u")
    assert out == "xin chào"
    assert fake.messages.last_kwargs["model"] == "claude-haiku-4-5-20251001"
    assert fake.messages.last_kwargs["max_tokens"] == 1024


def test_complete_smart_uses_smart_model():
    fake = FakeAnthropic()
    client = ClaudeClient(fake)
    client.complete(system="s", user="u", smart=True, max_tokens=200)
    assert fake.messages.last_kwargs["model"] == "claude-sonnet-4-6"
    assert fake.messages.last_kwargs["max_tokens"] == 200


def test_from_config_forwards_api_key():
    cfg = SimpleNamespace(anthropic_api_key="secret")
    with patch("anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value = SimpleNamespace(messages=None)
        client = ClaudeClient.from_config(cfg)
    MockAnthropic.assert_called_once_with(api_key="secret")
    assert isinstance(client, ClaudeClient)


def test_complete_json_returns_tool_input_and_forces_tool():
    class FakeMsgs:
        def __init__(self): self.last = None
        def create(self, **kw):
            self.last = kw
            return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input={"lop": 3, "mon": "toan"})])
    class Fake:
        def __init__(self): self.messages = FakeMsgs()
    fake = Fake()
    client = ClaudeClient(fake)
    schema = {"type": "object", "properties": {"lop": {"type": "integer"}}}
    out = client.complete_json(system="s", user="u", tool_name="classify", tool_schema=schema)
    assert out == {"lop": 3, "mon": "toan"}
    assert fake.messages.last["tool_choice"] == {"type": "tool", "name": "classify"}
    assert fake.messages.last["tools"][0]["name"] == "classify"
    assert fake.messages.last["tools"][0]["input_schema"] == schema
    assert fake.messages.last["model"] == "claude-haiku-4-5-20251001"  # cheap by default
