# DecisionOS v3.0.0 ? Portfolio Release

This is a locally verified research and engineering portfolio release. The [container prototype](docs/deployment/docker_setup.md) and [monitoring guide](docs/engineering/production_mlops_learning_guide.md) describe implemented pieces and remaining gaps; they are not deployment readiness claims.

An optional PostgreSQL operational record store has a separate migration history, but its migration has not yet been tested or applied. Local JSON remains the default.

DecisionOS is a research-driven retail predictive and prescriptive AI portfolio project. It helps investigate historical demand, compare forecasts and simulate replenishment where actual inventory data is unavailable. It uses historical M5 data, not live Walmart sales. The default hybrid recursively serves a registered Random Forest and uses a historical mean for its zero-average segment.

The stack combines PostgreSQL, Python, Pandas, scikit-learn, MLflow, FastAPI, React, TypeScript, Vite and ECharts. Inventory and costs are simulated; no real purchasing is performed.

- **Executive Overview** compares adjacent sales periods and shows demand trends, category contribution, and top products and stores.
- **Sales Intelligence** filters historical demand by state, store, category, and department, with daily, weekly, and monthly charts and a CSV export.
- **Product Intelligence** measures demand variability and zero-demand frequency, ranks products, compares up to five products, and shows product-store demand segments and volume-based ABC analysis.
- **Store & Category Intelligence** ranks stores, compares up to five store codes, analyzes states and merchandise hierarchies, and shows demand, contribution, and growth heatmaps.
- **Seasonality & Events** analyzes daily demand patterns, weekday-matched event comparisons, state-specific SNAP associations, and weekly price quotes for a selected item and store when the required data is available.
- **Business reports** export loaded executive, sales, product, store, calendar, and price analyses as timestamped CSV and Markdown files.
- **Demand Forecasting** and **Product & Store Intelligence** use searchable catalogs so users can select item and store codes directly.
- **Batch forecasting** previews a catalog scope, validates aligned pair histories, and aggregates eligible forecasts with coverage and model provenance.
- **Model Intelligence** exposes MLflow evaluation runs and registered model metadata.
- **Risk and simulated decisions** provide descriptive anomaly signals, inventory assumptions, replenishment recommendations, budget scenarios and historical policy replay.

## Architecture

```text
PostgreSQL actual sales -> training data validation -> lag and calendar features -> Random Forest
PostgreSQL pair history -> recursive Random Forest and hybrid policy -> FastAPI -> React
PostgreSQL actual sales -> analytics windows and summaries -> FastAPI -> React
MLflow tracking and registry -> model loading, run metadata, and evaluation history
Forecasts + simulated inventory assumptions -> decision simulation -> FastAPI -> React
```

| Location | Purpose |
|---|---|
| `src/decisionos/data/`, `features/`, `ml/` | Extraction and validation, feature generation, evaluation and forecasting |
| `src/decisionos/pipelines/` | Explicit training and evaluation workflows |
| `backend/`, `frontend/` | FastAPI services and the primary React interface |
| `dashboard/` | Legacy Streamlit fallback |
| `tests/unit/` | Synthetic and mocked automated tests |
| `experiments/`, `scripts/diagnostics/` | Manual model experiments, API and database checks, and MLflow utilities |
| `docs/engineering/`, `docs/experiments/` | Milestone guides, PostgreSQL review, and historical experiment evidence |

## Local setup

The primary React dashboard in `frontend/` supports analytics, individual and batch forecasting, MLflow metadata and report exports. The user completed manual browser acceptance testing and confirmed that the application works. The [feature checklist](docs/engineering/frontend_feature_parity.md) preserves earlier detailed tracking. The [migration guide](docs/engineering/frontend_migration_guide.md) describes the legacy Streamlit fallback.

Use Python 3.11. Run these commands from the repository root in PowerShell when setting up a new checkout.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Reuse an existing working environment and `.env` when available. Use `requirements.txt` for runtime dependencies alone. The development requirements include the research dependencies needed by the full default test suite; use `requirements-research.txt` independently for optional research workflows. The automated tests and health endpoint work without PostgreSQL data or an MLflow registry.

- Set `DATABASE_URL` to the existing DecisionOS PostgreSQL database using the `postgresql+psycopg` driver. The historical retail migration sources are missing, so schema bootstrap requires an independently provisioned database. The separate experimental operational migration does not recreate the retail schema and has not been verified. [Database review](docs/engineering/database_review.md)
- Keep the existing MLflow SQLite file and accessible artifact locations, or configure `MLFLOW_TRACKING_URI` for an existing store. The default resolves `mlflow.db` from the repository root. Forecasting loads `DecisionOS-Hybrid-Forecaster@candidate` by default. The API caches the model for the process, so restart the API after intentionally changing the alias or configuration.
- The dashboard uses `API_BASE_URL=http://127.0.0.1:8000` by default. Process environment variables override the project `.env`. Repository-relative model, forecast output, and tracking paths resolve from the project root.

Run the API and React dashboard in separate shells.

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
cd frontend
npm ci
npm run dev
```

Use Node.js 22.12 or newer in the Node 22 series. Open React at `http://localhost:5173` and API documentation at `http://127.0.0.1:8000/docs`. Run `npm run build` in `frontend/` for a production build. `GET /health` checks API liveness. Database- or registry-backed routes require their respective configured services. The legacy fallback remains available with `python -m streamlit run dashboard/app.py` from the project root.

## Analytics definitions

Overview, product and store summaries share the latest actual sales date across the platform. A product-store trend ends on that pair’s latest observation, which can be earlier. Each window includes both endpoints and reports `period_start`, `period_end`, and `period_days`.

| Field | Meaning |
|---|---|
| `observed_days` | Number of distinct days with sales records, including zero sales. `active_days` and `sales_days` retain this meaning where previously returned. |
| `positive_sales_days` | Observed days with positive sales for the selected scope. |
| `average_daily_demand` | Total demand divided by requested calendar days. |
| `average_observed_day_demand` | Total demand divided by observed days, or `null` when none were observed. |

A calendar-day denominator keeps period comparisons consistent and helps expose sparse observation coverage alongside the observed-day denominator. Analytics does not insert missing days into the returned trend. Forecasting requires each product-store history to contain one actual observation each day within that series.

Sales Intelligence compares equal-length periods and reports observed-day coverage for both. Demand is measured in units sold. An unobserved period has a null total, and percentage growth is undefined when previous demand was zero. The dashboard loads reports on demand and defaults to 30 days. [Sales Intelligence guide](docs/engineering/v1_2_2_sales_intelligence_guide.md)

## Tests and manual experiments

```powershell
python -m pytest -q
python -m pytest tests/unit/test_feature_parity.py -v
python -m ruff check src backend dashboard tests
python -m pip check
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
```

Default Pytest discovery is restricted to `tests/` and excludes marked integration tests. Run manual scripts from the project root with `python -m` so project imports resolve.

```powershell
python -m scripts.diagnostics.inspect_business_tables
python -m scripts.diagnostics.test_dashboard_analytics
python -m scripts.diagnostics.mlflow.test_mlflow_registry_load
```

The guarded scripts in `experiments/` can query substantial history, train models, or write artifacts. The MLflow setup and registration diagnostics can change tracking or registry state. Execute those explicitly only for the intended environment. The [implementation report](docs/engineering/v1_1_implementation_report.md) classifies every relocated script.

## Evaluation and limitations

The existing M5 28-day recursive evaluation for April 1–28, 2011 reported hybrid MAE **0.6198**, RMSE **1.9979**, and WAPE **77.03%** on 853,720 observations. The four seven-day rolling-origin folds in the same month reported average MAE **0.5866**, RMSE **1.8579**, and mean fold WAPE **73.2290%**. Those historical runs cover one month and were not repeated for V1.1. [28-day evaluation](docs/experiments/hybrid_model_evaluation.md) · [Rolling-origin evaluation](docs/experiments/rolling_origin_backtest.md)

Recursive forecasts reuse prior predictions and can accumulate errors across the horizon. Batch forecasting enforces configured synchronous workload limits and reports excluded histories. The direct prediction endpoint relies on caller-supplied feature values. Broad analytics can approach database time limits, as documented in the database review. Clean-install reproducibility remains unverified. Application health does not establish database or model readiness.

Forecast intervals and anomaly signals are experimental. Inventory balances, supplier inputs and costs are simulated. No real financial savings, causal event effects or population-wide model performance should be inferred. Docker execution and optional PostgreSQL operational migrations remain unverified; those migrations are unapplied and local JSON is the supported default operational record store. Public cloud deployment has not been performed. Production-grade authentication is incomplete; large-scale resumable forecasting and automated retraining and advanced model promotion remain future work. Forecast uncertainty validation is limited.

[V1.1 learning guide](docs/engineering/v1_1_learning_guide.md) · [V1.1 implementation report](docs/engineering/v1_1_implementation_report.md) · [Changelog](CHANGELOG.md)

[Product and store catalog guide](docs/engineering/v1_2_1_catalog_guide.md) · [Sales Intelligence guide](docs/engineering/v1_2_2_sales_intelligence_guide.md)

[Product Intelligence guide](docs/engineering/v1_2_3_product_intelligence_guide.md)

[Store & Category Intelligence guide](docs/engineering/v1_2_4_store_category_intelligence_guide.md)

[Batch forecasting guide](docs/engineering/v1_3_1_batch_hierarchical_forecasting_guide.md)

[Seasonality, Events & Reporting guide](docs/engineering/v1_2_5_seasonality_events_reporting_guide.md) · [Analytics performance plan](docs/engineering/analytics_performance_plan.md)


Forecasting research and measured bounded benchmark results are described in [RESEARCH.md](RESEARCH.md). The system overview is in [ARCHITECTURE.md](ARCHITECTURE.md).

Portfolio materials: [project summary](docs/portfolio/project_summary.md), [interview guide](docs/portfolio/interview_guide.md) and [demo guide](docs/portfolio/demo_guide.md). Collaboration notes are in [AI_COLLAB.md](AI_COLLAB.md).

A separate train-only stratified research study compared 12 forecasting methods on 60 historical pairs at three origins. Its sampled-cohort pooled WAPE ranged from 65.65% for TSB to 101.98% for the research Random Forest. The cohort was deliberately stratified and is not a population estimate. See the [benchmark report](docs/research/v1_4_1_forecasting_benchmark_report.md).

A matched V1.4.2 development study tested experimental feature families on the saved 60-pair cohort. The canonical LightGBM configuration outperformed the expanded sets on pooled WAPE in that sample. [Research results](docs/research/v1_4_2_feature_ablation_report.md)


## Deferred engineering

Future work includes verified PostgreSQL operational migrations, resumable forecast jobs, durable telemetry, controlled retraining and promotion, production-grade authentication, aggregate interval calibration, performance benchmarks and cloud deployment. Docker configuration is unverified. The served model has not been replaced.

DecisionOS retains modular FastAPI interfaces for external consumers. Generative and agentic AI is a separate project.
The V1.4.3 study evaluated model objectives and adaptive policies on development data, then assessed locked methods on a separate 30-pair chronological holdout. The pair-level WAPE leader showed substantial aggregate underprediction. [Optimization report](docs/research/v1_4_3_optimization_report.md)

Predictive intelligence now includes selectable statistical forecast strategies, pair-level empirical intervals, bounded locally persisted forecast runs, and descriptive demand and price risk signals. The hybrid remains the default. The [evaluation](docs/research/predictive_intelligence_evaluation.md) records calibration and synthetic limitations, and the [architecture](docs/architecture/predictive_intelligence_architecture.md) describes local persistence.

Prescriptive intelligence adds a clearly simulated inventory and decision workspace. Saved single-pair point forecasts can be combined with user-supplied stock, lead-time and cost assumptions for replenishment, scenarios and a bounded historical policy replay. These are simulated decisions, not actual inventory records or purchases. [Prescriptive evaluation](docs/research/prescriptive_intelligence_evaluation.md)
