from pathlib import Path
import pytest
from ai_tutor.config import load_config


def test_load_config_builds_paths_and_dirs(tmp_path: Path):
    env = {"ANTHROPIC_API_KEY": "k", "TELEGRAM_BOT_TOKEN": "t"}
    cfg = load_config(root=tmp_path, env=env)
    assert cfg.anthropic_api_key == "k"
    assert cfg.telegram_bot_token == "t"
    assert cfg.inbox_dir == tmp_path / "inbox"
    assert cfg.db_path == tmp_path / "data" / "ai_tutor.db"
    assert cfg.inbox_dir.is_dir()
    assert cfg.failed_dir.is_dir()
    assert cfg.data_dir.is_dir()


def test_load_config_missing_key_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        load_config(root=tmp_path, env={"ANTHROPIC_API_KEY": "k"})
