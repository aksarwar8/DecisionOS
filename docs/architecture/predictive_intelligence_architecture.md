# Predictive intelligence architecture

```mermaid
flowchart LR
  UI[React forecast page] --> API[FastAPI]
  API --> Scope[Catalog scope and workload limits]
  Scope --> DB[(PostgreSQL historical sales)]
  DB --> Validate[Validate pair histories]
  Validate --> Chunks[Bounded pair chunks]
  Chunks --> Hybrid[Registered hybrid]
  Chunks --> Baselines[TSB, moving average, seasonal naive]
  Hybrid --> Aggregate[Point forecast aggregation]
  Baselines --> Aggregate
  Aggregate --> Runs[Atomic local run snapshots]
  API --> Interval[Pair-level historical residual intervals]
  API --> Risk[Past-only demand and price signals]
  Runs --> UI
  Interval --> UI
  Risk --> UI
```

PostgreSQL stores existing source data. Run snapshots currently use a local directory controlled by `DECISIONOS_FORECAST_RUN_DIR`, defaulting to `forecast_runs/` under the project root. Files are excluded from Git. No schema change or migration is applied. Snapshots are not an authenticated or multi-host database. Back up the directory if run history matters.

Execution remains synchronous and bounded by existing pair and row limits. Chunk size is 1–100 and defaults to 50. Status writes are atomic file replacements, and no incomplete chunk forecast is presented as a complete run. Eligibility exclusions are returned with a completed run. A failure after some chunks records a failed status and completed-pair count. Process termination can leave a running status that requires operational review. There is no worker queue or automatic restart.

Uncertainty is provided only for a single pair. Summing marginal interval bounds does not yield a calibrated aggregate interval. Demand and price signals are descriptive statistical alerts, with no real-world fraud or stockout attribution.
