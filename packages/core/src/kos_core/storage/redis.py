"""Cliente de Redis (bus de eventos y broker de Celery)."""

from __future__ import annotations

from redis import Redis as SyncRedis
from redis.asyncio import Redis

from kos_core.config import Settings
from kos_core.schemas.events import EventBase

# Canal único del bus de eventos internos (doc 06 §3).
EVENTS_CHANNEL = "kos:events"


def create_client(settings: Settings) -> Redis:
    client: Redis = Redis.from_url(settings.redis_url)
    return client


def create_sync_client(settings: Settings) -> SyncRedis:
    """Cliente síncrono para contextos sin event loop (tasks de Celery)."""
    client: SyncRedis = SyncRedis.from_url(settings.redis_url)
    return client


async def ping(client: Redis) -> None:
    await client.ping()


def publish_event_sync(client: SyncRedis, event: EventBase) -> None:
    client.publish(EVENTS_CHANNEL, event.model_dump_json())


async def publish_event(client: Redis, event: EventBase) -> None:
    await client.publish(EVENTS_CHANNEL, event.model_dump_json())
