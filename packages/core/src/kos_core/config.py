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

    # Herramientas externas (ResearchAgent, doc 06 §4, Sprint 20)
    github_token: str = ""
    brave_search_api_key: str = ""

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

    # LLM cloud opt-in (ADR-0007): por tarea, explícito, off por defecto. Solo el
    # Planner (generación de plan) y el WritingAgent (síntesis) son configurables
    # a cloud; la ingesta, el grafo y los embeddings siguen 100% locales.
    kos_planner_llm_provider: str = "ollama"
    kos_writing_llm_provider: str = "ollama"
    openai_api_key: str = ""
    openai_llm_model: str = "gpt-4o-mini"
    openai_base_url: str = ""
    llm_observatory_url: str = ""
    llm_observatory_token: str = ""

    # --- Despliegue gestionado (doc 14; ADR-0008/0009/0010) ---------------
    # Todo lo de abajo está apagado o vacío por defecto: el modo local-first de
    # doc 09 no necesita ninguna de estas variables.

    # Postgres/Redis gestionados entregan **una URL**, no cinco piezas sueltas.
    # Si está puesta, gana sobre postgres_* (ver `postgres_dsn`).
    database_url: str = ""
    # Railway duerme un servicio solo si no emite tráfico saliente (doc 14 §2.2):
    # en este modo los pools no mantienen conexiones ociosas abiertas.
    kos_serverless_mode: bool = False

    # Autenticación (ADR-0010): lista `nombre:clave` separada por comas. Vacía =
    # solo conexiones locales, que es el modo local de siempre.
    kos_api_keys: str = ""
    kos_rate_limit_per_minute: int = 120
    # Límite aparte y más estricto para lo que gasta LLM cloud por petición.
    kos_rate_limit_llm_per_minute: int = 20

    # Cadena de proveedores LLM (ADR-0008): `openai,openrouter`. Vacía = el
    # comportamiento por tarea de ADR-0007 (cloud → Ollama).
    kos_llm_provider_chain: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_llm_model: str = "openai/gpt-4o-mini"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_llm_model: str = "llama-3.3-70b-versatile"

    # Embeddings (ADR-0008): sigue siendo bge-m3 a 1024 dimensiones; lo único
    # que cambia es quién lo sirve. `openai_compatible` = endpoint hospedado.
    kos_embedding_provider: str = "ollama"
    kos_embedding_base_url: str = ""
    kos_embedding_api_key: str = ""
    kos_embedding_model: str = "bge-m3"

    # Disparo inmediato de la ingesta (doc 14 §5). Con el worker apagado entre
    # ciclos y el vault en su volumen, la API no puede ingerir por sí misma: lo
    # que hace es pedirle a Railway que ejecute ahora el servicio cron.
    railway_api_token: str = ""
    railway_cron_service_id: str = ""
    railway_environment_id: str = ""
    railway_api_url: str = "https://backboard.railway.com/graphql/v2"
    # Cada disparo arranca un contenedor: se limita por hora, no por minuto.
    kos_sync_now_per_hour: int = 4
    # A partir de cuántas horas sin ejecución del cron se considera parada la
    # ingesta (lo que `/v1/ops/status` reporta como `stale`).
    kos_cron_stale_hours: int = 18
    # Build estático de `apps/web` servido por la propia API (doc 14 §3): un
    # servicio menos en Railway. Vacío en local, donde el web corre en Vite.
    kos_web_dist: str = ""

    # Memoria (v0.4, doc 04 §3): cada cuánto corre la consolidación (episódica
    # repetida → semántica) y la media vida del decaimiento de `salience`.
    kos_memory_consolidation_hours: int = 24
    kos_memory_salience_half_life_days: float = 30.0

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
        """DSN de SQLAlchemy. `database_url` (Supabase, Railway, cualquier
        gestionado) gana sobre las piezas sueltas: los proveedores entregan una
        URL completa, con su `?sslmode=require`, no host/puerto por separado."""
        if self.database_url:
            return _as_async_dsn(self.database_url)
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def api_keys(self) -> dict[str, str]:
        """`{nombre: clave}` a partir de `kos_api_keys` (ADR-0010). Una entrada
        sin `:` se registra con el nombre `default`."""
        keys: dict[str, str] = {}
        for raw in self.kos_api_keys.split(","):
            entry = raw.strip()
            if not entry:
                continue
            name, _, secret = entry.partition(":")
            if secret:
                keys[name.strip()] = secret.strip()
            else:
                keys["default"] = name.strip()
        return keys

    @property
    def llm_provider_chain(self) -> list[str]:
        """Proveedores en orden de intento (ADR-0008); vacía si no se configuró."""
        return [item.strip() for item in self.kos_llm_provider_chain.split(",") if item.strip()]


_ASYNC_DRIVER = "postgresql+psycopg"


def _as_async_dsn(url: str) -> str:
    """Normaliza la URL de un Postgres gestionado al driver async del proyecto.

    `postgres://` y `postgresql://` (lo que entregan Supabase y Railway) usarían
    el driver síncrono por defecto de SQLAlchemy. Se respeta el driver si la URL
    ya trae uno explícito, y se conserva intacto el query string (`sslmode`,
    `options`), que es obligatorio contra los gestionados.
    """
    scheme, separator, rest = url.partition("://")
    if not separator:
        return url
    if "+" in scheme:
        return url
    if scheme in {"postgres", "postgresql"}:
        return f"{_ASYNC_DRIVER}://{rest}"
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
