from src.env_config import load_env_value


def test_load_env_value_prefers_os_environ(tmp_path, monkeypatch):
    monkeypatch.setenv("SOME_KEY", "from-environ")
    assert load_env_value("SOME_KEY", tmp_path / "no_such.env") == "from-environ"


def test_load_env_value_reads_from_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("SOME_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('# comment\nSOME_KEY="from-file"\n', encoding="utf-8")
    assert load_env_value("SOME_KEY", env_file) == "from-file"


def test_load_env_value_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("SOME_KEY", raising=False)
    assert load_env_value("SOME_KEY", tmp_path / "no_such.env") is None
