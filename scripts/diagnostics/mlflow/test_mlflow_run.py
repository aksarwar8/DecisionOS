if __name__ == "__main__":

    from src.decisionos.config import get_settings

    import mlflow
    from mlflow.tracking import MlflowClient

    mlflow.set_tracking_uri(get_settings().resolve_tracking_uri())

    client = MlflowClient()

    run_id = "e40f828d365144209d5f7951feba7f14"

    run = client.get_run(run_id)

    print("\nDECISIONOS MLFLOW RUN DETAILS")
    print("=" * 60)

    print("Run ID:", run.info.run_id)
    print("Status:", run.info.status)
    print("Experiment ID:", run.info.experiment_id)

    print("\nPARAMETERS")
    print("-" * 60)

    for key, value in run.data.params.items():
        print(f"{key}: {value}")

    print("\nMETRICS")
    print("-" * 60)

    for key, value in run.data.metrics.items():
        print(f"{key}: {value}")

    print("\nARTIFACTS")
    print("-" * 60)

    artifacts = client.list_artifacts(run_id)

    for artifact in artifacts:
        print(artifact.path, "| Directory:", artifact.is_dir)

    print("\nMLflow run inspection completed.")
