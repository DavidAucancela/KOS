from kos_core.templater import render_template

_PLANTILLA_REAL = """---
title: "<% tp.file.title %>"
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
tags: [tipo/ejercicio]
status: borrador
---

<%* /*
Plantilla: Ejercicio.
Tags recomendados: area/{...}
*/ %>

# <% tp.file.title %>

## Enunciado

…
"""


def test_sustituye_titulo_en_frontmatter_y_heading() -> None:
    out = render_template(_PLANTILLA_REAL, title="Fawn", date="2026-07-20")
    assert 'title: "Fawn"' in out
    assert "# Fawn" in out


def test_sustituye_fecha_en_ambos_campos() -> None:
    out = render_template(_PLANTILLA_REAL, title="Fawn", date="2026-07-20")
    assert out.count("2026-07-20") == 2


def test_quita_el_bloque_de_comentario_templater() -> None:
    out = render_template(_PLANTILLA_REAL, title="Fawn", date="2026-07-20")
    assert "<%*" not in out
    assert "Tags recomendados" not in out


def test_plantilla_sin_placeholders_no_se_rompe() -> None:
    texto = "# Nota fija\n\nsin nada que sustituir"
    assert render_template(texto, title="X", date="2026-01-01") == texto
