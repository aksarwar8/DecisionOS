# Five-minute local walkthrough

Start the configured PostgreSQL and MLflow services, then start the API and React frontend using the [README](../../README.md). Use the React interface at `http://localhost:5173`. Historical data, the registered model and MLflow artifacts must already exist. This walkthrough is a manual acceptance checklist, not a claim that every browser workflow was tested.

1. **Business context (one minute):** open Executive Overview or Sales Intelligence, load a bounded period and explain that this is historical unit demand, not revenue or live sales.
2. **Product exploration (one minute):** search for a product code, select a store and inspect its historical demand and coverage. Missing observations are not automatically zero.
3. **Forecasting (one minute):** select one product-store pair and a 14-day horizon. Preview and generate a small TSB or hybrid batch forecast; explain model provenance and any exclusions. Avoid a full-business run.
4. **Simulated decision (one minute):** select the saved single-pair forecast in Inventory & Decisions. Use a lead time that leaves seven additional forecast days; generate a recommendation and a demand-change scenario. Explain that stock and costs are synthetic and no purchase is made.
5. **Research and operations (one minute):** show Model Intelligence, available historical model results and API readiness. Explain the small-cohort holdout, uncertain intervals, JSON snapshots and unverified infrastructure. Export a loaded report if desired.

For the default seven-day lead time, a seven-day forecast is insufficient for the seven additional review days. Use a 14-day or 28-day forecast instead. Check light/dark mode and report downloads separately during browser acceptance.

Release preparation on 2026-11-26 started temporary API and Vite processes. HTTP checks returned 200 for database readiness, product and store catalog, pair trends, demand risk, assumptions, model info, monitoring, individual TSB forecast, batch preview, a saved batch run and retrieval, 14-day replenishment recommendation, scenario and historical simulation. The React entry HTML returned 200. The temporary processes were stopped. This was an HTTP-level check; no interactive browser walkthrough was performed.
