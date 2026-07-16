"""Cliente de Neo4j (ADR-0003: fuente de verdad de las relaciones)."""

from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase

from kos_core.config import Settings


def create_driver(settings: Settings) -> AsyncDriver:
    return AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )


async def ping(driver: AsyncDriver) -> None:
    await driver.verify_connectivity()
