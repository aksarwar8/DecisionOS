
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from mlflow.tracking import MlflowClient
from mlflow.exceptions import MlflowException

from backend.services.model_service import configure_mlflow
from src.decisionos.config import get_settings


router = APIRouter(
    prefix="/model",
    tags=["Model"],
)

def get_mlflow_client():
    """Create an MLflow tracking client."""
    return MlflowClient(tracking_uri=configure_mlflow())


def format_run(run):
    """Convert an MLflow run into an API-friendly dictionary."""

    start_time = run.info.start_time

    return {
        "run_id": run.info.run_id,
        "run_name": run.data.tags.get("mlflow.runName", "Unnamed"),
        "run_type": run.data.tags.get("run_type", "training"),
        "status": run.info.status,
        "start_time": (
            datetime.fromtimestamp(
                start_time / 1000,
                tz=timezone.utc,
            ).isoformat()
            if start_time
            else None
        ),
        "metrics": run.data.metrics,
        "params": run.data.params,
        "tags": run.data.tags,
    }


def get_experiment_and_runs(client):
    """Retrieve the DecisionOS experiment and its runs."""

    experiment = client.get_experiment_by_name(
        get_settings().mlflow_experiment_name
    )

    if experiment is None:
        raise HTTPException(
            status_code=404,
            detail="DecisionOS MLflow experiment not found.",
        )

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["attributes.start_time DESC"],
        max_results=100,
    )

    return experiment, runs


@router.get("/info")
def get_model_info():
    """Return information about the active registered model."""
    settings = get_settings()

    client = get_mlflow_client()

    try:
        model = client.get_model_version_by_alias(
            name=settings.model_name,
            alias=settings.model_alias,
        )

        return {
            "model_name": model.name,
            "version": model.version,
            "alias": settings.model_alias,
            "status": model.status,
            "model_uri": settings.registered_model_uri,
        }

    except MlflowException as exc:
        if exc.error_code != "RESOURCE_DOES_NOT_EXIST":
            raise
        raise HTTPException(
            status_code=404,
            detail="Registered model not found.",
        ) from exc


@router.get("/metrics")
def get_model_metrics():
    """Return the latest evaluation metrics."""

    client = get_mlflow_client()

    experiment, runs = get_experiment_and_runs(client)

    evaluation_runs = [
        run for run in runs
        if run.data.tags.get("run_type") == "evaluation"
        and run.info.status == "FINISHED"
    ]

    if not evaluation_runs:
        return {
            "experiment_name": experiment.name,
            "message": "No completed evaluation runs found.",
            "latest_evaluation": None,
        }

    latest = evaluation_runs[0]

    return {
        "experiment_name": experiment.name,
        "latest_evaluation": {
            "run_id": latest.info.run_id,
            "training_run_id": latest.data.tags.get(
                "training_run_id"
            ),
            "start_time": (
                datetime.fromtimestamp(
                    latest.info.start_time / 1000,
                    tz=timezone.utc,
                ).isoformat()
                if latest.info.start_time
                else None
            ),
            "metrics": latest.data.metrics,
            "params": latest.data.params,
        },
        "total_evaluation_runs": len(evaluation_runs),
    }


@router.get("/runs")
def get_model_runs(limit: int = 20):
    """Return recent training and evaluation runs."""

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100.",
        )

    client = get_mlflow_client()

    experiment, runs = get_experiment_and_runs(client)

    selected_runs = runs[:limit]

    training_runs = [
        format_run(run)
        for run in selected_runs
        if run.data.tags.get("run_type") != "evaluation"
    ]

    evaluation_runs = [
        format_run(run)
        for run in selected_runs
        if run.data.tags.get("run_type") == "evaluation"
    ]

    return {
        "experiment_name": experiment.name,
        "total_runs_returned": len(selected_runs),
        "training_runs": training_runs,
        "evaluation_runs": evaluation_runs,
    }


@router.get("/registry")
def get_model_registry():
    """Return registered model versions and aliases."""
    settings = get_settings()

    client = get_mlflow_client()

    try:
        active_model = client.get_model_version_by_alias(
            name=settings.model_name,
            alias=settings.model_alias,
        )

        versions = client.search_model_versions(
            filter_string=f"name='{settings.model_name}'"
        )

        version_details = []

        for version in versions:
            version_details.append({
                "version": version.version,
                "status": version.status,
                "creation_timestamp": version.creation_timestamp,
                "aliases": getattr(version, "aliases", []),
                "description": version.description,
            })

        return {
            "model_name": settings.model_name,
            "active_alias": settings.model_alias,
            "active_version": active_model.version,
            "model_uri": settings.registered_model_uri,
            "versions": version_details,
            "total_versions": len(version_details),
        }

    except MlflowException as exc:
        if exc.error_code != "RESOURCE_DOES_NOT_EXIST":
            raise
        raise HTTPException(
            status_code=404,
            detail="Model registry information unavailable.",
        ) from exc
