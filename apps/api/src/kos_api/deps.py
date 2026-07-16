"""Dependencias FastAPI: settings y clientes compartidos de app.state (doc 10 §2)."""

from __future__ import annotations

from fastapi import Request
from minio import Minio
from neo4j import AsyncDriver
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_core.config import Settings, get_settings


def settings_dep() -> Settings:
    """Configuración tipada; cacheada a nivel de proceso."""
    return get_settings()


def postgres_engine(request: Request) -> AsyncEngine:
    engine: AsyncEngine = request.app.state.postgres_engine
    return engine


def neo4j_driver(request: Request) -> AsyncDriver:
    driver: AsyncDriver = request.app.state.neo4j_driver
    return driver


def redis_client(request: Request) -> Redis:
    client: Redis = request.app.state.redis_client
    return client


def minio_client(request: Request) -> Minio:
    client: Minio = request.app.state.minio_client
    return client
