"""Tests de la heurística de intención de plantilla (Sprint 8)."""

import pytest

from kos_api.services.intent_service import detect_template_intent

POSITIVOS = [
    "quiero crear información para describir un proyecto, ¿qué plantilla me sirve o me "
    "conviene crear una nueva?",
    "¿existe alguna plantilla para proyectos?",
    "¿tienes una plantilla de reunión?",
    "¿cómo creo una nota para un proyecto nuevo?",
    "plantilla para describir un proyecto",
    # Órdenes imperativas (encontradas en pruebas manuales, Sprint 8 seguimiento)
    "voy a tener una reunion, crea una planilla para los apuntes",
    "crea una plantilla para los apuntes",
    "hazme una plantilla de reunión",
    "necesito una plantilla para un concepto",
    "crea un archivo nuevo utilizando una plantilla acorde al tema",
]

NEGATIVOS = [
    "¿qué es Tuti?",
    "resume el proyecto UB APP",
    "¿cómo funciona FastAPI?",
    "explícame la arquitectura de agentes",
]


@pytest.mark.parametrize("query", POSITIVOS)
def test_detecta_intencion_de_plantilla(query: str) -> None:
    assert detect_template_intent(query) is True


@pytest.mark.parametrize("query", NEGATIVOS)
def test_no_detecta_intencion_en_preguntas_normales(query: str) -> None:
    assert detect_template_intent(query) is False
