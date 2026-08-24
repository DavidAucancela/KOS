from kos_workers.pipeline._json_utils import strip_code_fence


def test_quita_fence_con_json() -> None:
    assert strip_code_fence("```json\n[1, 2]\n```") == "[1, 2]"


def test_quita_fence_sin_lenguaje() -> None:
    assert strip_code_fence("```\n[1, 2]\n```") == "[1, 2]"


def test_sin_fence_no_cambia() -> None:
    assert strip_code_fence("[1, 2]") == "[1, 2]"


def test_espacios_sobrantes_se_recortan() -> None:
    assert strip_code_fence("  ```json\n[1]\n```  ") == "[1]"


def test_prosa_despues_del_cierre_se_descarta() -> None:
    """Hallazgo real verificando doc 12 §4 en vivo (2026-08-19): llama3.2
    agrega explicaciones después del cierre pese a "SOLO JSON" — antes el
    regex no pelaba nada en este caso (el `$` no matcheaba con texto detrás)
    y el JSON quedaba pegado a la prosa, rompiendo `json.loads` en silencio."""
    raw = '```json\n[{"a": 1}]\n```\n\nEsta relación se basa en el texto proporcionado.'
    assert strip_code_fence(raw) == '[{"a": 1}]'


def test_prosa_antes_y_despues_se_descarta() -> None:
    raw = "Acá está el resultado:\n```json\n[1, 2]\n```\nEspero que te sirva."
    assert strip_code_fence(raw) == "[1, 2]"
