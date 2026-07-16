import pytest

from kos_core.config import Settings


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.postgres_dsn == "postgresql+psycopg://kos:kos_dev_password@localhost:5432/kos"
    assert settings.ollama_embedding_model == "bge-m3"


def test_settings_desde_variables_de_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "db.interna")
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "otro-modelo")
    settings = Settings(_env_file=None)
    assert settings.postgres_host == "db.interna"
    assert settings.ollama_embedding_model == "otro-modelo"
