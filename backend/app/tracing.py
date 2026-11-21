"""Metadata-only MLflow traces for CFO requests."""

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _configure_experiment() -> None:
    """Select the experiment in the workspace of the application service account."""
    import mlflow

    mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", "autonomous-cfo-agents"))


@contextmanager
def trace_span(name: str) -> Iterator[dict]:
    """Export only caller-supplied operational metadata. Keep application failures independent of export."""
    attributes = {}
    manager = None
    span = None
    if os.environ.get("MLFLOW_TRACKING_URI"):
        try:
            import mlflow

            _configure_experiment()
            manager = mlflow.start_span(name=name)
            span = manager.__enter__()
        except Exception as error:
            logger.warning("MLflow span unavailable (%s)", type(error).__name__)

    try:
        yield attributes
    except Exception as error:
        attributes["error_type"] = type(error).__name__
        raise
    finally:
        if span is not None and manager is not None:
            try:
                span.set_attributes(attributes)
                if "error_type" in attributes:
                    span.set_status("ERROR")
            except Exception as error:
                logger.warning("MLflow metadata unavailable (%s)", type(error).__name__)
            finally:
                try:
                    # Raw exceptions can include response bodies. Export only the error class above.
                    manager.__exit__(None, None, None)
                except Exception as error:
                    logger.warning("MLflow export failed (%s)", type(error).__name__)
