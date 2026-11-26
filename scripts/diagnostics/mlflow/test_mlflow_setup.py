if __name__ == "__main__":

    from src.decisionos.config import get_settings

    import mlflow
    settings = get_settings()

    # Create local artifact directory.
    settings.project_path(settings.mlflow_artifact_dir).mkdir(
        parents=True,
        exist_ok=True,
    )

    # Use SQLite as the tracking backend.
    mlflow.set_tracking_uri(settings.resolve_tracking_uri(require_existing=False))

    # Create or select the DecisionOS experiment.
    mlflow.set_experiment(settings.mlflow_experiment_name)

    # Retrieve experiment information.
    experiment = mlflow.get_experiment_by_name(
        settings.mlflow_experiment_name
    )

    print("\nMLFLOW CONFIGURATION")
    print("-" * 50)

    print("MLflow version:", mlflow.__version__)
    print("Experiment name:", experiment.name)
    print("Experiment ID:", experiment.experiment_id)
    print("Artifact location:", experiment.artifact_location)

    print("\nMLflow setup completed successfully.")
