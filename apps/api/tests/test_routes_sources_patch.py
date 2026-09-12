"""Validación de `PATCH /v1/sources/{id}` (ADR-0007): el endpoint existe para el
interruptor `cloud_safe`, no para repuntar la configuración del conector."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kos_api.routes.sources import SourceConfigPatch


def test_cloud_safe_booleano_es_valido() -> None:
    assert SourceConfigPatch(config={"cloud_safe": True}).config == {"cloud_safe": True}


def test_rechaza_claves_de_conector() -> None:
    """`config` se fusiona con shallow-merge en el JSONB; sin allowlist, este
    PATCH podría repuntar el vault de la fuente."""
    with pytest.raises(ValidationError, match="vault_path"):
        SourceConfigPatch(config={"cloud_safe": True, "vault_path": "/otro/vault"})


def test_rechaza_cloud_safe_no_booleano() -> None:
    with pytest.raises(ValidationError, match="booleano"):
        SourceConfigPatch(config={"cloud_safe": "true"})


def test_rechaza_config_vacio() -> None:
    with pytest.raises(ValidationError, match="nada que actualizar"):
        SourceConfigPatch(config={})
