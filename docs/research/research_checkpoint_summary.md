# Research checkpoint summary

The V1.4.1–1.4.3 research code and reports are local and reviewable. The V1.4.3 30-pair holdout found lower pair WAPE for LightGBM L1 than TSB but substantial underprediction and worse sampled-total WAPE. No replacement was selected. MLflow experiment 4 contains the development and holdout runs named in the [optimization report](v1_4_3_optimization_report.md).

Optional research-only dependency versions are in `requirements-research.txt`. Small derived charts under `docs/research/figures/` are suitable for review. Raw datasets, local model binaries, MLflow stores, local forecast snapshots, virtual environments, caches and build products are excluded by ignore rules. This is a checkpoint proposal, not a commit.
