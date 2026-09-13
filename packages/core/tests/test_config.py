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


def test_database_url_gana_sobre_piezas_sueltas(monkeypatch: pytest.MonkeyPatch) -> None:
    """Los gestionados (Supabase, Railway) entregan una URL, no host/puerto (doc 14 §6)."""
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
    monkeypatch.setenv(
        "DATABASE_URL", "postgres://u:p@db.supabase.co:5432/postgres?sslmode=require"
    )
    settings = Settings(_env_file=None)
    assert settings.postgres_dsn == (
        "postgresql+psycopg://u:p@db.supabase.co:5432/postgres?sslmode=require"
    )


def test_database_url_respeta_driver_explicito(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@host/db")
    assert Settings(_env_file=None).postgres_dsn == "postgresql+asyncpg://u:p@host/db"


def test_api_keys_con_nombre(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADR-0010: `nombre:clave`, para revocar un cliente sin tocar los demás."""
    monkeypatch.setenv("KOS_API_KEYS", "web:k1, mac:k2 ,")
    assert Settings(_env_file=None).api_keys == {"web": "k1", "mac": "k2"}


def test_api_keys_sin_nombre_es_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOS_API_KEYS", "solo-una-clave")
    assert Settings(_env_file=None).api_keys == {"default": "solo-una-clave"}


def test_api_keys_vacias_por_defecto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KOS_API_KEYS", raising=False)
    settings = Settings(_env_file=None)
    assert settings.api_keys == {}
    assert settings.llm_provider_chain == []
    assert settings.kos_serverless_mode is False
    assert settings.kos_embedding_provider == "ollama"


def test_llm_provider_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOS_LLM_PROVIDER_CHAIN", "openai, openrouter")
    assert Settings(_env_file=None).llm_provider_chain == ["openai", "openrouter"]
