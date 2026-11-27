# Changelog

## Unreleased — production engineering in progress

- Added process-local request counters, a database readiness probe and a descriptive drift helper.
- Added an unverified container prototype and documented the outstanding production work.
- Added an opt-in PostgreSQL operational store and separate migration chain; migration testing is blocked by database permissions. Added bounded historical drift diagnostics and a demonstration mutation-token safeguard.
- Added portfolio documentation and guarded experimental migrations against accidental use of the public schema. Local JSON remains the default.
- Added optional research dependencies to development requirements so the default research unit tests can be collected in CI.

## 1.4.3 — Model optimization and adaptive forecasting research

- Evaluated bounded intermittent-demand parameter grids, LightGBM objectives, a two-stage hurdle model, a pooled direct model and a train-only adaptive rule.
- Locked development selections before a separate 30-pair chronological holdout and recorded research results in MLflow.
- Preserved the served candidate. The measured pair-level and aggregate accuracy trade-off did not justify packaging a deployment candidate.

## Unreleased

- Added simulated inventory assumptions, deterministic replenishment, budget allocation, scenarios, historical policy comparisons and simulated decision reviews.
- Added the React inventory and decisions workspace and a bounded historical simulation report.

- Added experimental statistical forecasting methods, empirical pair intervals, chunked local run snapshots, and demand and price risk signals.
- Added React forecast selection, interval display, run retrieval and a risk page. Synthetic interval undercoverage remains an open limitation.

- Defined the predictive and prescriptive AI roadmap and the external API boundary for a separate Generative and Agentic AI project.

## 1.4.2 — Experimental feature research

- Added a separate versioned research feature contract, bounded calendar/price extraction and matched LightGBM feature ablations.
- Recorded three-origin 60-pair results and a separate MLflow research run. Production features and the candidate model remain unchanged.
- Corrected the historical V1.4.1 research-runner dispatch and clarified that its recorded LightGBM result included the hybrid zero-history policy.

## 1.4.1 — Forecast evaluation research

- Added fixed reference and intermittent-demand baselines, strict research metrics, chronological window helpers and synthetic checks.
- Added a bounded PostgreSQL benchmark with per-origin research forest training and local results.
- Added train-only demand characterization, seeded stratified cohort sampling, LightGBM comparison, per-series RMSSE and matched hierarchical metrics.
- Recorded a bounded 60-pair, three-origin comparison, research charts and a separate verified MLflow run. Results remain scoped to the sampled cohort.


## 1.3.2 — Professional React Frontend

- Made React the primary dashboard with catalog-filtered analytics, comparisons, heatmaps, seasonality, pricing, forecast workload preview and batch runs, MLflow views, and loaded-result exports. Streamlit remains a legacy fallback while detailed feature acceptance continues.

## 1.3.1

- Added bounded common-origin batch forecasting, scope previews, pair exclusions, and bottom-up breakdowns.
- Added forecast workload limits and a batch mode in the Demand Forecasting dashboard.

## 1.2.5

- Added historical seasonality, calendar-event and event-relative comparisons, and state-specific SNAP analysis.
- Added conditional weekly price intelligence with price-match coverage, demand comparisons around observed quote changes, and estimated value for matched sales.
- Added timestamped CSV reports and deterministic Markdown summaries of loaded analyses.
- Documented query performance and a future pre-aggregation plan.

## 1.2.4

- Added store drill-downs, demand and growth rankings, and comparisons for up to five stores.
- Added state, category, and department reports with historical trends, product counts, and contribution.
- Added store-category, store-department, and state-category heatmaps and CSV exports. Missing cells remain distinct from recorded zero demand.

## 1.2.3

- Added Product Intelligence with product-day metrics, growth and variability rankings, five-product comparison, and CSV exports.
- Exposed historical product-store demand segments using the existing forecasting thresholds.
- Added volume-based ABC analysis with cumulative contribution across the full filtered scope before pagination.

## 1.2.2

- Enhanced Executive Overview with period-over-period demand, category contribution, and top product and store rankings.
- Added Sales Intelligence with catalog filters, selectable trend intervals, contribution charts, and CSV export.
- Added typed analytics endpoints and an on-demand bundled report that reuses the optimized actual-sales anchor.

## 1.2.1

- Added searchable product and store catalog endpoints with metadata filters and stable product pagination.
- Replaced manual ID entry with catalog selectors on the Forecasting and Product & Store Intelligence pages.

## 1.1 stabilization

- Optimized the actual-sales anchor with existing PostgreSQL indexes and consolidated overview aggregation.
- Updated Streamlit layout calls to use the supported width argument.

## 1.1.0

- Explicit canonical feature order and a synthetic training-serving regression test, including the ISO-week rollover.
- Shared validation for complete daily product-store history at training and recursive forecasting boundaries.
- Actual-sales analytics anchors, explicit window bounds and demand denominators, and input-matched dashboard results.
- Shared environment settings, guarded MLflow tracking paths, and UTF-8 Python dependency manifests.
- Standard application logging and request-correlated, safe API error responses.
- Side-effect-free default unit test discovery, guarded manual diagnostics, and a GitHub Actions quality workflow.
- Read-only PostgreSQL schema and planner review, setup documentation, and a V1.1 engineering learning guide.
