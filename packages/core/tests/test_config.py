import pytest

from kos_core.config import Settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("OPENAI_API_KEY", "LLM_OBSERVATORY_URL", "LLM_OBSERVATORY_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)
    assert settings.postgres_dsn == "postgresql+psycopg://kos:kos_dev_password@localhost:5432/kos"
    assert settings.ollama_embedding_model == "bge-m3"
    # ADR-0007: cloud apagado por defecto.
    assert settings.kos_planner_llm_provider == "ollama"
    assert settings.kos_writing_llm_provider == "ollama"
    assert settings.openai_api_key == ""
    assert settings.llm_observatory_url == ""


def test_llm_cloud_settings_desde_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOS_WRITING_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_OBSERVATORY_URL", "http://localhost:3002")
    settings = Settings(_env_file=None)
    assert settings.kos_writing_llm_provider == "openai"
    assert settings.openai_api_key == "sk-test"
    assert settings.llm_observatory_url == "http://localhost:3002"


def test_settings_desde_variables_de_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "db.interna")
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "otro-modelo")
    settings = Settings(_env_file=None)
    assert settings.postgres_host == "db.interna"
    assert settings.ollama_embedding_model == "otro-modelo"
