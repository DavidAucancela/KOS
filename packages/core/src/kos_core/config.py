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
    # Cada cuánto Celery beat dispara kos.sync_all_sources (doc 05 §2: "las
    # fuentes sin notificaciones se cubren con polling programado").
    kos_sync_poll_seconds: int = 300
    # Fuente por defecto donde `notes_service` crea notas nuevas desde el chat.
    kos_default_vault_source: str = "vault-real"

    # Ahorro de recursos (doc 09 §8): apaga la infra Docker sin uso y la
    # enciende bajo demanda. Off por defecto: no debe activarse solo por
    # correr la API en tests o en un entorno sin `docker compose` a mano.
    kos_guardian_enabled: bool = False
    kos_compose_file: str = "docker-compose.yml"
    kos_activity_file: str = "/tmp/kos-guardian-activity"
    kos_idle_stop_minutes: int = 20
    kos_guardian_start_timeout_seconds: float = 45.0

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
