"""Frontmatter YAML de las notas de Obsidian → metadata (doc 05 §2)."""

from __future__ import annotations

from typing import Any

import yaml  # type: ignore[import-untyped]


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Separa el bloque YAML inicial (``---``…``---``) del cuerpo de la nota.

    Nunca lanza: frontmatter ausente, sin cierre, inválido o que no sea un
    mapeo YAML → ``({}, texto íntegro)``.
    """
    if not text.startswith(("---\n", "---\r\n")):
        return {}, text

    lines = text.splitlines(keepends=True)
    for index in range(1, len(lines)):
        if lines[index].strip() != "---":
            continue
        raw_block = "".join(lines[1:index])
        body = "".join(lines[index + 1 :])
        try:
            data = yaml.safe_load(raw_block)
        except yaml.YAMLError:
            return {}, text
        if not isinstance(data, dict):
            return {}, text
        return data, body

    # Delimitador de apertura sin cierre: no es frontmatter.
    return {}, text
