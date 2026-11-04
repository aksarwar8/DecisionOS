
from pathlib import Path
import joblib

# Project root directory
BASE_DIR = Path(__file__).resolve().parents[2]

# Saved LightGBM model path
MODEL_PATH = BASE_DIR / "models" / "product_store_lightgbm_model.pkl"


def load_model():
    """Load the trained LightGBM model."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at: {MODEL_PATH}"
        )

    model = joblib.load(MODEL_PATH)
    return model
