from pathlib import Path

import pytest


@pytest.fixture()
def mini_vault() -> Path:
    return Path(__file__).parent / "fixtures" / "mini_vault"
