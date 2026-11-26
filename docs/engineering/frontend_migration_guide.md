# React migration guide

React provides a routed dashboard with independent analytical workflows, shared controls and responsive visualizations. FastAPI continues to own database access, metrics, model policy and forecast generation. Streamlit remains available for comparison and fallback.

## Run locally

Use Node 22.12 or newer in the Node 22 series. Start FastAPI from the repository root with `python -m uvicorn backend.main:app --reload`. In another PowerShell window, run `cd frontend`, `npm ci` and `npm run dev`. Open http://localhost:5173. Run `npm run build` to create a production bundle in `dist`.

## Browser acceptance checklist

1. Open Executive Overview and load a 30-day report. Check growth, category contribution and leading products and stores.
2. Open Sales Intelligence, select a state, and load a weekly report. Change the state and confirm the old results disappear. Load again and download both report formats.
3. Compare two products at one store. Confirm each item has a separate line. Check the six ranking options, segment results and the ABC curve with the 80% and 95% markers.
4. Compare two stores. Inspect category composition and switch heatmap dimensions and metrics. Hover a numeric zero and compare it with an empty cell.
5. Load a seasonal analysis, then choose an event name or type for the event-window request. Check baseline and coverage fields. Check SNAP results with a specific state.
6. Choose a product and store in Price Intelligence. Check the two axes, quote coverage and estimated sales value units.
7. Generate a seven-day individual forecast. Preview and run the single-pair batch scope. Verify origin, coverage, history, prediction rows and breakdowns. Preview the entire business and confirm generation is unavailable.
8. Load model info, registry, runs and metrics separately. Toggle dark mode, reload and confirm the preference survives. Check the sidebar and filters at a narrow width.

## Study order

Start with the API client and route shell. Read the catalog controls and one analytics view next. Follow the forecast preview into the batch request, then read the chart adapter and reporting formatter. Finish with the workflow tests.

Useful interview topics include the difference between editable and submitted filters, cache key design, request cancellation, missing values in charts, and enforcing workload limits server-side.

The live HTTP spot checks used bounded scopes. PostgreSQL computations can still take several seconds. Keep broad reports explicitly triggered and use results already loaded for exports. Browser acceptance is tracked separately in the feature parity checklist.

## Live HTTP checks

The existing API returned HTTP 200 for the following bounded requests. Latencies are single local observations.

| Request | Time |
|---|---:|
| Catalog products, 2 rows | 0.453 s |
| Event catalog | 2.139 s |
| Model information | 23.973 s |
| Product 4 at store 1, 30-day price report | 8.712 s |
| Products 4 and 5 at store 1, 30-day comparison | 13.787 s |
| Store 1 and FOODS, seven-day store/category matrix | 7.462 s |
| Single-pair forecast preview | 0.213 s |
| Full-business forecast preview | 0.504 s |
| Single-pair seven-day batch forecast | 18.855 s |

The batch returned seven rows, an origin of 2016-04-24, complete scope coverage and a total prediction of 16.88566 units. The business preview reported 30,490 candidate pairs and an estimated 213,430 rows. The running API allowed up to 100 pairs and 2,800 rows synchronously. The Vite proxy also returned the FastAPI health response.

These requests verified backend HTTP behavior. Browser interaction and chart rendering still require the acceptance steps above.

React is the primary interface. The user confirmed that it works in a browser. Streamlit remains a legacy fallback while individual workflows receive detailed acceptance.
