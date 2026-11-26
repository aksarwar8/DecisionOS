from pathlib import Path
from unittest.mock import Mock

import pytest

from src.decisionos import config
from src.decisionos.ml import registry


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    for setting in config.fields(config.Settings):
        monkeypatch.delenv(setting.name.upper(), raising=False)
    config.get_settings.cache_clear()
    yield tmp_path
    config.get_settings.cache_clear()


def test_defaults_resolve_from_project_root_without_creating_sqlite(project, monkeypatch):
    elsewhere = project / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    settings = config.get_settings()
    assert settings.database_url is None
    assert settings.registered_model_uri == "models:/DecisionOS-Hybrid-Forecaster@candidate"
    assert settings.project_path(settings.model_dir) == project / "models" / "trained"
    with pytest.raises(FileNotFoundError, match="missing or empty"):
        settings.resolve_tracking_uri()
    assert not (project / "mlflow.db").exists()


def test_environment_overrides_dotenv_and_secrets_stay_out_of_repr(project, monkeypatch):
    (project / ".env").write_text(
        "DATABASE_URL=postgresql+psycopg://user:example-secret@localhost/db\n"
        "MODEL_ALIAS=from-file\nMLFLOW_TRACKING_URI=sqlite:///state/registry.db\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MODEL_ALIAS", "override")
    monkeypatch.setenv("API_BASE_URL", "http://test.invalid:9000")
    path = project / "state" / "registry.db"
    path.parent.mkdir()
    path.write_bytes(b"placeholder for path validation")
    settings = config.get_settings()
    assert "example-secret" in settings.database_url
    assert "example-secret" not in repr(settings)
    assert settings.model_alias == "override"
    assert settings.api_base_url == "http://test.invalid:9000"
    assert settings.resolve_tracking_uri() == f"sqlite:///{Path(path).as_posix()}"


def test_local_model_read_and_write_use_the_same_configured_path(project, monkeypatch):
    monkeypatch.setenv("MODEL_DIR", "local/models")
    expected = project / "local" / "models" / "example.joblib"
    model = object()
    dump = Mock(side_effect=lambda value, path: path.touch())
    load = Mock(return_value=model)
    monkeypatch.setattr(registry.joblib, "dump", dump)
    monkeypatch.setattr(registry.joblib, "load", load)
    assert registry.save_model(model, expected.name) == expected
    assert registry.load_model(expected.name) is model
    dump.assert_called_once_with(model, expected)
    load.assert_called_once_with(expected)
