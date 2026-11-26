import logging

from pathlib import Path

import joblib


from src.decisionos.config import get_settings


logger = logging.getLogger(__name__)


def save_model(
    model,
    model_name: str = "random_forest.joblib",
) -> Path:
    """
    Save a trained ML model to disk.
    """

    settings = get_settings()
    model_dir = settings.project_path(settings.model_dir)
    model_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    model_path = model_dir / model_name

    joblib.dump(
        model,
        model_path,
    )

    logger.info("Model saved to %s", model_path)

    return model_path


def load_model(
    model_name: str = "random_forest.joblib",
):
    """
    Load a previously saved ML model.
    """

    settings = get_settings()
    model_path = settings.project_path(settings.model_dir) / model_name

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}"
        )

    model = joblib.load(model_path)

    logger.info("Model loaded from %s", model_path)

    return model
