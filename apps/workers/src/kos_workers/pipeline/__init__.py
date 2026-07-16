"""Pipeline del parser: etapas componibles y puras (doc 05 §3, doc 10 §3)."""

from kos_workers.pipeline.base import (
    DEFAULT_STAGES,
    PIPELINE_VERSION,
    Stage,
    bootstrap,
    run_pipeline,
)

__all__ = ["DEFAULT_STAGES", "PIPELINE_VERSION", "Stage", "bootstrap", "run_pipeline"]
