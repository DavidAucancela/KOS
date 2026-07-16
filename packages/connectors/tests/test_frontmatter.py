from kos_connectors.obsidian.frontmatter import split_frontmatter


def test_frontmatter_valido() -> None:
    text = "---\ntitle: Nota\ntags:\n  - a\n  - b\n---\n# Cuerpo\n"
    data, body = split_frontmatter(text)
    assert data == {"title": "Nota", "tags": ["a", "b"]}
    assert body == "# Cuerpo\n"


def test_frontmatter_ausente() -> None:
    text = "# Solo cuerpo\n"
    assert split_frontmatter(text) == ({}, text)


def test_frontmatter_yaml_invalido_no_lanza() -> None:
    text = "---\nkey: [sin cerrar\n---\ncuerpo\n"
    assert split_frontmatter(text) == ({}, text)


def test_frontmatter_que_no_es_mapeo() -> None:
    text = "---\n- a\n- b\n---\ncuerpo\n"
    assert split_frontmatter(text) == ({}, text)


def test_frontmatter_sin_cierre() -> None:
    text = "---\ntitle: Nota\nsin cierre\n"
    assert split_frontmatter(text) == ({}, text)
