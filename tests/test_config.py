from pathlib import Path
import pytest
from ai_tutor.config import load_config


def test_default_provider_is_gemini(tmp_path: Path):
    cfg = load_config(root=tmp_path, env={"GEMINI_API_KEY": "g", "TELEGRAM_BOT_TOKEN": "t"})
    assert cfg.llm_provider == "gemini"
    assert cfg.llm_api_key == "g"
    assert cfg.llm_base_url == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert cfg.llm_cheap_model == "gemini-2.5-flash"
    assert cfg.llm_smart_model == "gemini-2.5-pro"
    assert cfg.inbox_dir.is_dir() and cfg.db_path == tmp_path / "data" / "ai_tutor.db"


def test_select_openai_and_override_models(tmp_path: Path):
    cfg = load_config(root=tmp_path, env={
        "LLM_PROVIDER": "openai", "OPENAI_API_KEY": "o", "TELEGRAM_BOT_TOKEN": "t",
        "LLM_SMART_MODEL": "gpt-5",
    })
    assert cfg.llm_provider == "openai" and cfg.llm_base_url is None
    assert cfg.llm_cheap_model == "gpt-4o-mini"
    assert cfg.llm_smart_model == "gpt-5"  # override thắng


def test_missing_provider_key_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        load_config(root=tmp_path, env={"LLM_PROVIDER": "grok", "TELEGRAM_BOT_TOKEN": "t"})


def test_missing_telegram_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        load_config(root=tmp_path, env={"GEMINI_API_KEY": "g"})


def test_unknown_provider_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        load_config(root=tmp_path, env={"LLM_PROVIDER": "llama", "TELEGRAM_BOT_TOKEN": "t"})
