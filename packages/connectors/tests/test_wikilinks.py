from kos_connectors.obsidian.wikilinks import extract_tags, extract_wikilinks


def test_wikilinks_simples_alias_y_seccion() -> None:
    text = "Ver [[Nota]], [[Otra|un alias]] y [[Tercera#Sección]]."
    assert extract_wikilinks(text) == ["Nota", "Otra", "Tercera"]


def test_wikilinks_alias_con_seccion() -> None:
    assert extract_wikilinks("[[Docker#Volúmenes|volúmenes]]") == ["Docker"]


def test_wikilinks_sin_duplicados_en_orden() -> None:
    text = "[[B]] y [[A]] y de nuevo [[B|alias]]"
    assert extract_wikilinks(text) == ["B", "A"]


def test_wikilink_a_seccion_del_propio_archivo_se_ignora() -> None:
    assert extract_wikilinks("Ver [[#Sección local]]") == []


def test_tags_basicos_y_anidados() -> None:
    text = "Nota con #python y #kos/vision repetido #python"
    assert extract_tags(text) == ["python", "kos/vision"]


def test_encabezados_markdown_no_son_tags() -> None:
    text = "# Título\n## Subtítulo\nCuerpo con #tag-real\n"
    assert extract_tags(text) == ["tag-real"]


def test_fragmento_de_url_no_es_tag() -> None:
    text = "Ver https://ejemplo.com/docs#anclas y http://x/#frag pero sí #valido"
    assert extract_tags(text) == ["valido"]
