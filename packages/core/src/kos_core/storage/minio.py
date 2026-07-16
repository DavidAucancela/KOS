"""Cliente de MinIO (blobs de documentos originales). API síncrona: envolver
en un hilo (`asyncio.to_thread`) desde contextos async."""

from __future__ import annotations

import io

from minio import Minio

from kos_core.config import Settings


def create_client(settings: Settings, *, secure: bool = False) -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        secure=secure,
    )


def ping(client: Minio, bucket: str) -> None:
    """Conexión OK si no lanza; el bucket puede no existir todavía."""
    client.bucket_exists(bucket)


def ensure_bucket(client: Minio, bucket: str) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def put_blob(
    client: Minio,
    bucket: str,
    key: str,
    data: bytes,
    *,
    content_type: str = "application/octet-stream",
) -> str:
    """Guarda un blob inmutable (doc 05 §6: ningún dato original se pierde)."""
    ensure_bucket(client, bucket)
    client.put_object(bucket, key, io.BytesIO(data), length=len(data), content_type=content_type)
    return key
