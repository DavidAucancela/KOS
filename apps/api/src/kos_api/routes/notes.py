"""POST /v1/notes — crear una nota desde una plantilla real del vault (doc 06 §4,
versión directa en la API — ver nota en ese doc)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine

from kos_api.deps import postgres_engine, settings_dep
from kos_api.services import notes_service
from kos_core.config import Settings

router = APIRouter(prefix="/v1/notes", tags=["notes"])


class NoteIn(BaseModel):
    template: str = Field(min_length=1, examples=["MaquinaHTB"])
    folder: str = Field(min_length=1, examples=["Security/HackTheBox/Máquinas"])
    title: str = Field(min_length=1, examples=["Fawn"])


class NoteOut(BaseModel):
    path: str
    deferred: bool = False
    """True cuando la nota quedó encolada porque este proceso no tiene el vault
    (doc 14 §5): la ruta es la prevista, todavía no existe el archivo."""


@router.post("", response_model=NoteOut, status_code=201)
async def create_note(
    body: NoteIn,
    engine: AsyncEngine = Depends(postgres_engine),
    settings: Settings = Depends(settings_dep),
) -> NoteOut:
    try:
        note_path, deferred = await notes_service.create_note_or_enqueue(
            engine,
            settings,
            source_name=settings.kos_default_vault_source,
            template_name=body.template,
            folder=body.folder,
            title=body.title,
        )
    except notes_service.VaultSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except notes_service.TemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except notes_service.NoteAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return NoteOut(path=note_path, deferred=deferred)
