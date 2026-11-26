"""Environment-backed settings shared by the API, dashboard and pipelines."""

import os
from dataclasses import dataclass, field, fields
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORECAST_ARTIFACT_NAME = "forecast_output.csv"


@dataclass(frozen=True)
class Settings:
    database_url: str | None = field(default=None, repr=False)
    mlflow_tracking_uri: str = field(default="sqlite:///mlflow.db", repr=False)
    mlflow_experiment_name: str = "DecisionOS Demand Forecasting"
    model_name: str = "DecisionOS-Hybrid-Forecaster"
    model_alias: str = "candidate"
    api_base_url: str = "http://127.0.0.1:8000"
    app_env: str = "local"
    log_level: str = "INFO"
    model_dir: str = "models/trained"
    forecast_output_dir: str = "."
    mlflow_artifact_dir: str = "mlartifacts"
    forecast_max_pairs: int = 100
    forecast_max_rows: int = 2800

    @staticmethod
    def project_path(path: str) -> Path:
        return (PROJECT_ROOT / path).resolve()

    @property
    def registered_model_uri(self) -> str:
        return f"models:/{self.model_name}@{self.model_alias}"

    def resolve_tracking_uri(self, *, require_existing: bool = True) -> str:
        """Resolve local paths and require an existing store for ordinary use."""
        uri = self.mlflow_tracking_uri
        scheme, delimiter, location = uri.partition(":///")
        if scheme.split("+", 1)[0] == "sqlite":
            if not delimiter or not location or location.startswith("file:"):
                raise ValueError("Configure MLflow SQLite with an ordinary database file path.")
            filename, separator, options = location.partition("?")
            path = self.project_path(filename)
            if require_existing and (not path.is_file() or path.stat().st_size == 0):
                raise FileNotFoundError("The configured MLflow SQLite database is missing or empty.")
            return f"{scheme}{delimiter}{path.as_posix()}{separator}{options}"
        if uri.startswith("file:"):
            parsed = urlsplit(uri)
            if parsed.netloc not in {"", "localhost"}:
                raise ValueError("Use a local file URI for the MLflow tracking directory.")
            uri = url2pathname(parsed.path)
        if "://" not in uri:
            path = self.project_path(uri)
            if require_existing and not path.is_dir():
                raise FileNotFoundError("The configured MLflow tracking directory is missing.")
            return path.as_uri()
        return uri


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Read the project .env once. Process environment overrides its values."""
    dotenv = dotenv_values(PROJECT_ROOT / ".env")
    values = {}
    for setting in fields(Settings):
        key = setting.name.upper()
        value = os.environ.get(key, dotenv.get(key))
        if value is not None:
            values[setting.name] = value
    return Settings(**values)
