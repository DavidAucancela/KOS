from kos_workers.pipeline._json_utils import strip_code_fence


def test_quita_fence_con_json() -> None:
    assert strip_code_fence("```json\n[1, 2]\n```") == "[1, 2]"


def test_quita_fence_sin_lenguaje() -> None:
    assert strip_code_fence("```\n[1, 2]\n```") == "[1, 2]"


def test_sin_fence_no_cambia() -> None:
    assert strip_code_fence("[1, 2]") == "[1, 2]"


def test_espacios_sobrantes_se_recortan() -> None:
    assert strip_code_fence("  ```json\n[1]\n```  ") == "[1]"
