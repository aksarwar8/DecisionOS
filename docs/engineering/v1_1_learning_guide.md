# DecisionOS V1.1 engineering learning guide

Start with the existing parity test and follow a sales row through the training and serving paths. Then study the analytics and configuration paths. Finish with error handling, verification, and release documentation. The [implementation report](v1_1_implementation_report.md) records the exact scope and verification limits.

## Step 1C — Validate daily sales before computing lags

Previously, `shift(7)` meant seven rows back, and training accepted internal gaps and duplicate dates. The forecast API had its own gap check over distinct dates, so repeated dates could still occupy multiple lag positions. Transforming quantities to `int32` unconditionally could also hide an invalid negative fractional observation or overflow a large value before validation.

`validate_historical_sales` in `src/decisionos/data/validate.py` verifies required columns, non-null identifiers, valid calendar dates, real finite nonnegative quantities, unique daily keys, and continuity. It returns parsed dates aligned to the original rows. The implementation first rejects duplicate normalized date keys, then checks each pair's row count against the number of days between its endpoints.

```python
observations = history[keys].assign(date=dates)
spans = observations.groupby(keys, sort=False, observed=True)["date"].agg(
    ["min", "max", "size"]
)
expected_days = (spans["max"] - spans["min"]).dt.days + 1
```

Once keys are unique, equality with the inclusive span proves every date is present. This works on shuffled rows and allows different spans for different pairs. The ML feature builder and recursive forecaster still sort before constructing sequence-based features. `prepare_ml_dataset` and `recursive_forecast` each validate at entry, outside all prediction loops. The hybrid forecaster delegates historical validation to recursion. The API's duplicate gap logic was removed. `transform_sales` keeps its compact integer representation when lossless and preserves other numeric values for validation. Generic `validate_dataframe` still handles structural checks and logs duplicate reports.

Study `data/validate.py` → `data/transform.py` → `ml/dataset.py` → `ml/forecast.py` → `ml/hybrid.py` → `backend/services/forecast_service.py` → `tests/unit/test_historical_sales.py`. Learn how data contracts make row-based features meaningful and how vectorized checks avoid a per-row loop.

**Interview explanation.** “I enforce unique daily keys and prove continuity using each pair’s inclusive date span. The same contract protects training from misleading row offsets and serving from malformed history.”

**Verification.** `python -m pytest tests/unit/test_historical_sales.py tests/unit/test_feature_parity.py -q` passed 16 cases. Production-scale memory and timing remain unmeasured. The validator cannot infer observations outside a series’ first or last day. Missing observations require an upstream decision.

## Step 2 — Anchor analytics to observed sales

Product and store summaries previously ended on the latest calendar date, which can include dates beyond sales. Overview already used actual sales and the trend used pair history. A date-free aggregate could look like a valid empty summary. The dashboard stored results under a fixed key and could show the old result after input changes.

`backend/services/analytics_service.py` now shares this actual-sales anchor across overview, product and store queries.

```sql
SELECT c.date AS latest_date
FROM calendar c
WHERE EXISTS (SELECT 1 FROM sales s WHERE s.calendar_id = c.id)
ORDER BY c.date DESC
LIMIT 1
```

`summarize_period` computes inclusive bounds, observed and positive-sales day counts, and calendar-day and observed-day averages. For a four-day window with 12 units on one day and a zero record on another, the averages are 3 and 6. `active_days` and `sales_days` remain compatibility fields for observed days. With an existing entity and no observations in the platform window, the observed-day average is null. Without a platform anchor, the API returns 404. The trend keeps its latest pair observation and reports its own bounds. PostgreSQL enforces nonnegative quantities, so counting a platform date with any positive sale is equivalent to positive aggregate demand for that date.

`backend/api/schemas/analytics.py` defines the common period fields and the dedicated `OverviewResponse`. The route uses typed request constraints, distinguishes missing results with `AnalyticsNotFoundError`, and wraps pair trend rows in the period contract. The dashboard's request wrappers already forward the decoded JSON, so analytics did not need a wrapper change. In `dashboard/app.py`, result visibility is tied to the selected input tuple. Inputs changing or a refresh starting clears the stored result.

Study the service SQL → response schemas and route → dashboard state checks → `tests/unit/test_analytics.py` and analytics cases in `test_api.py`. Learn about inclusive SQL windows, aggregate cardinality, denominators, and keeping UI state tied to the request that produced it.

**Interview explanation.** “A calendar row only proves a date exists. I anchor platform comparisons to sales-backed dates and expose the denominator and coverage separately.”

**Verification.** `python -m pytest tests/unit/test_analytics.py -q` passed three tests. Mocked API coverage checked bounds serialization, trend arithmetic, invalid inputs, and missing resources. A Streamlit `AppTest` run with mocked responses verified the forecast and analytics panels render and clear when inputs change. Live PostgreSQL planned the changed SQL. Query result integration and a live browser session remain unverified.

## Step 3 — Read PostgreSQL plans before proposing indexes

The repository had extraction SQL and a table diagnostic, with only compiled Alembic caches visible. Index candidates and table size initially came from assumptions. The new [database review](database_review.md) records what the configured database actually reported.

The inspection used `BEGIN READ ONLY`, short statement and lock timeouts, schema and index catalogs, `pg_stat_user_tables`, and plain `EXPLAIN` with application binds. Estimated sales rows were 58,330,342. The existing unique sales index already covers product, store and calendar. The calendar already has a unique date index. Store and overview plans scanned the sales table. The proposed store/calendar and calendar-only indexes require separate evaluation because index maintenance and disk usage affect ingestion.

Read the database review → `src/decisionos/data/extract.py` → `src/decisionos/data/extract_forecast.py` → analytics SQL. Learn how a composite index’s leading columns affect selective lookup, and how reported costs and row estimates differ from execution measurements.

**Interview explanation.** “I inspected the catalog first and used planner-only EXPLAIN. I found the pair index already serves the critical lookup, then narrowed the follow-up to scan-heavy query patterns.”

**Verification.** All five plans in the database review were collected. Exact counts, measured latency, index benefits, and schema bootstrap remain unverified. No DDL, migrations, or data changes were performed.

## Step 4 — Centralize settings and local paths

The backend and pipelines each specified a tracking URI, while registry filenames and the dashboard URL depended on duplicated values or the current working directory. A relative SQLite URI could initialize a different tracking database when invoked from another directory.

`src/decisionos/config.py` reads a project-root `.env` through the existing `python-dotenv` dependency. It puts process overrides on top and caches a frozen `Settings` instance. The dataclass avoids an extra settings dependency in this environment. Secrets-bearing database and tracking fields are excluded from the settings representation. Database settings are optional at load time. The engine and MLflow client are created only when their callers need them.

```python
settings = get_settings()
tracking_uri = settings.resolve_tracking_uri()
model_uri = settings.registered_model_uri
```

`resolve_tracking_uri` makes local paths project-relative and checks the SQLite file exists and is nonempty before normal use. The manual setup utility explicitly opts into initializing a store. `forecast_output.csv` remains the MLflow artifact basename shared by forecasting and evaluation. `MODEL_DIR` controls the local Joblib directory, while `MODEL_NAME` and `MODEL_ALIAS` select the registry identity. Defaults keep the existing `candidate` alias and local artifact paths. `.env.example` documents the supported keys, and `.gitignore` excludes actual environment files.

Study `.env.example` → `config.py` → data extraction → `backend/services/model_service.py` and `backend/api/routes/model.py` → pipelines and local registry → `dashboard/api_client.py` → `tests/unit/test_config.py`. Learn environment precedence, lazy initialization, and the difference between a filesystem artifact and a model registry reference.

**Interview explanation.** “I resolve local paths from one stable root and fail early for absent tracking storage. API modules can still load for health checks and tests without live services.”

**Verification.** The configured SQLite file resolved and the default registry identity matched. Tests exercised default settings, environment overrides, secret representation, project-relative model I/O with mocked serialization, and API registry name/alias wiring. The actual registered model was not loaded as part of verification. Restart a running API when changing cached settings or alias selection.

## Step 5 — Make dependencies explicit

The original `requirements.txt` had a UTF-16 BOM, resembled an environment freeze, and omitted core runtime packages including MLflow, Streamlit and Plotly. The replacement is UTF-8 and pins direct runtime versions from the working Python 3.11 environment. `requirements-dev.txt` includes runtime requirements, then adds Pytest, HTTPX and Ruff. The configured PostgreSQL driver is Psycopg 3. Existing model artifact metadata specified `skops` serialization, so that package is explicit.

Study both manifests → README install commands → the configuration and imports of API, pipeline and dashboard modules. Learn the difference between a direct dependency, a transitive dependency, and a cross-platform lock.

**Interview explanation.** “I pinned the dependencies the application and its existing model artifact actually use, while leaving the installer to resolve transitives.”

**Verification.** `python -m pip check` found no broken requirements. `python -m pip install --dry-run --no-index -r requirements-dev.txt` confirmed the existing environment satisfies the manifests. Only Ruff was installed. A fresh resolution and installation on another machine remains unverified.

## Step 6 — Handle API errors at the right boundary

Prediction previously exposed exception text in a 500 response. Forecast and prediction also treated every `ValueError` as a client problem. Application workflows reported progress with print statements.

`src/decisionos/logging_config.py` configures standard timestamped logging from settings. `backend/main.py` assigns IDs, adds an `X-Request-ID` response header and handles unexpected exceptions centrally with `logger.exception`. The error response carries the same ID with a generic message. Forecast and prediction catch specific expected input errors, and FastAPI keeps its 422 validation behavior. Model routes only translate MLflow's known missing-resource code. The forecasting/evaluation pipeline and training/data helpers use module loggers.

Study logging configuration → FastAPI middleware and error handler → typed route exceptions → mocked API tests. Learn how an exception type communicates ownership of a failure and how response IDs connect a report to internal logs. The service can run with ordinary Python logging handlers.

**Interview explanation.** “I keep actionable input failures public and give unexpected failures a stable response. The same request ID reaches the caller and the internal traceback.”

**Verification.** The API tests exercised successful responses, 422 input validation, expected 400/404 responses and generic 500 responses. The error tests checked the request ID against the captured log. The IDs are process-generated and there is no distributed tracing backend.

## Step 7 — Keep experiments outside automated discovery

Thirty files named `test_*.py` lived at the root or under `scripts/`. They invoked database extraction, evaluation, training, local artifact I/O, or MLflow as soon as imported. Two additional database diagnostics also did work on import.

The research workflows now live under `experiments/`, diagnostics under `scripts/diagnostics/`, and the four MLflow tools under `scripts/diagnostics/mlflow/`. Their executable bodies are guarded by `if __name__ == "__main__":`. The `pyproject.toml` setting `testpaths = ["tests"]` narrows discovery, and the default marker expression excludes integration tests. The feature parity file stayed in place. The [implementation report](v1_1_implementation_report.md) classifies every relocated file.

Study `pyproject.toml` → a guarded script → `.gitignore` → README commands. Learn the difference between module import and script execution. Invoke manual scripts with `python -m` from the root so their absolute imports resolve.

**Interview explanation.** “Discovery itself can execute top-level Python. I restricted default collection and also made the manual modules safe to import.”

**Verification.** Default collection found 45 cases only under `tests/unit/`. The source and migration-source paths were checked against ignore patterns, along with the sample configuration, actual environment files and generated artifacts. Imports were checked without running the experiment bodies. Experiment outputs were not regenerated. Some scripts depend on historical run IDs, model files or the absent prices table.

## Step 8 — Cover the core behavior with small tests

The existing parity tests covered the feature boundary. The expanded suite covers invalid observations, exact lag and rolling calculations, group isolation, expected dates, positivity clipping, recursive feedback, thresholds at 0, 1 and 5, analytics, settings and API behavior. For leakage, `tests/unit/test_forecasting.py` replaces the target quantity and confirms its historical features are identical. The recursive stub records each call to show how clipped or fractional predictions feed the next rolling window.

`evaluate_forecasts` now rejects inputs whose shapes differ or are not vectors before applying NumPy’s valid-pair mask. A scalar-length vector could broadcast in the old mask and fail later with a misleading error. The new evaluation tests preserve the paired finite filter, manual MAE/RMSE/WAPE expectations, and the undefined WAPE when actual demand totals zero.

Study `test_feature_parity.py` → `test_forecasting.py` → `ml/evaluate.py` and its tests → the API and settings tests. Learn to pin observable contracts using counterexamples and controlled test doubles.

**Interview explanation.** “The leakage test changes the current label and proves the past-only features are invariant. The recursive test makes the next model input observable without fitting a model.”

**Verification.** `python -m pytest -q` ran 45 passing cases, including all five parity cases, with zero failures and skips. Pandas deprecation warnings remain. All tests use in-memory data, temporary files, or mocked services.

## Step 9 — Run the same quality checks in CI

The repository had no pipeline for linting and safe test execution. `.github/workflows/ci.yml` checks out the code with read-only permission, sets up Python 3.11 with pip caching, installs development requirements, and runs Ruff and Pytest. The runner uses no database service or registry credentials.

```text
python -m ruff check src backend dashboard tests
python -m pytest -q
```

The Ruff baseline checks syntax and Pyflakes correctness across runtime and test directories. Manual experiments remain outside this initial scope. Lint exposed missing variables during the config wiring and those were corrected.

Study the workflow → `pyproject.toml` → dependency manifests. Learn how CI makes verification repeatable and how a targeted lint baseline keeps the maintenance cost reasonable. [GitHub checkout](https://github.com/actions/checkout) · [GitHub Python setup](https://github.com/actions/setup-python)

**Interview explanation.** “The same commands run locally and in CI. Database-free tests mean pull requests can be verified with minimal permissions.”

**Verification.** Ruff 0.17.6 passed the configured scope and the local safe suite passed. Remote execution is pending.

## Step 10 — Document what is ready

The README previously contained only the title. It now explains the architecture, local setup, config, analytics definitions, startup and manual commands, historical evaluation, and remaining limits. `CHANGELOG.md` records V1.1. The implementation report lists observed results and pending work, and this guide connects the code changes to the engineering lessons.

Study README → changelog → the implementation report → database review and historical experiment notes. Learn to distinguish a validated local change from a deployment claim and a historical result from a new benchmark.

**Interview explanation.** “I treated the documentation as part of the release contract. It tells a new maintainer which checks are safe to run and which services and artifacts need separate setup.”

**Verification.** README paths and module names were checked against the repository. The local development quality checks passed. Fresh installation, interactive browser smoke testing, full-service operational readiness and remote CI remain pending.
