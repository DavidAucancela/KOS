"""Configuración tipada de KOS (doc 09 §5): todo por variables de entorno."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # PostgreSQL + pgvector
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "kos"
    postgres_user: str = "kos"
    postgres_password: str = "kos_dev_password"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "kos_dev_password"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "kos"
    minio_root_password: str = "kos_dev_password"
    minio_bucket: str = "kos-documents"

    # Ollama (ADR-0006: local-first)
    ollama_base_url: str = "http://localhost:11434"
    # Modelo ligero por defecto (~2 GB); subir a qwen2.5/qwen3 si hay recursos.
    ollama_llm_model: str = "llama3.2:latest"
    ollama_embedding_model: str = "bge-m3"

    # Fuentes de conocimiento
    obsidian_vault_path: str = ""

    # Aplicación
    kos_env: str = "development"
    kos_log_level: str = "INFO"
    # Puerto donde el worker Celery expone /metrics (doc 09 §6): no tiene
    # servidor HTTP propio, así que Prometheus scrapea este puerto directo.
    kos_worker_metrics_port: int = 9808
    # Apaga la etapa cara de grafo (Sprint 6) sin tocar código: útil para una
    # reingesta masiva (`kos reindex`) donde no se quiere duplicar la carga de
    # LLM por nota mientras solo se necesita recuperar la búsqueda.
    kos_graph_sync_enabled: bool = True

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
