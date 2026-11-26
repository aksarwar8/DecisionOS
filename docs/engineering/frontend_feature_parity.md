# React feature parity

React is the primary interface and Streamlit is a legacy fallback. The user confirmed that React works in their browser. This checklist tracks acceptance of individual workflows.

| Streamlit workflow | React destination | Status |
|---|---|---|
| Executive metrics, demand history, category contribution and leading items and stores | Executive Overview | Implemented. Browser verification pending. |
| Filtered sales, growth, trends, breakdowns and rankings | Sales Intelligence | Implemented with the combined sales report. Browser verification pending. |
| Product drill-down, six ranks, comparisons, variability, segments and ABC | Product Intelligence | Implemented. Scoped comparison returned HTTP 200. Pareto uses backend cumulative values from the current result page. |
| Store drill-down, rankings, comparisons, states, category and department composition | Store & Category | Implemented. Mocked comparison test covers selection and request parameters. Browser verification pending. |
| Store/category, store/department and state/category matrices | Store & Category | Implemented with units, contribution and growth views. Scoped store/category returned HTTP 200. |
| Product, store and pair-level historical details | Product–Store History | Implemented against the three original endpoints. Browser verification pending. |
| Five seasonality modes, event catalog, weekday-matched baseline, event windows and SNAP | Seasonality & Events | Implemented. Event catalog returned HTTP 200. Browser verification pending. |
| Weekly pricing, demand, quote coverage, price changes and descriptive relationship | Price Intelligence | Implemented. Scoped price request returned HTTP 200. Browser verification pending. |
| Individual forecast | Demand Forecasting | Implemented. Individual endpoint supplies forecast rows and selected model per day. Use the single-pair batch scope for aligned history and registry provenance. |
| Batch forecast scopes, preview and coverage | Demand Forecasting | Implemented. Live preview verified for one pair and entire business. Entire business remains preview-only in React. |
| MLflow info, registry, runs and historical evaluation | Model Intelligence | Implemented as separate views. Live model info returned HTTP 200. Browser verification pending. |
| Reports | Business Reports and analysis pages | Implemented. Downloads use the current response and represent the loaded result page when server pagination applies. |
| Health and feature capabilities | System Status | Implemented. Live API health verified. |

The Windows computer-use tool ended the session because it could not verify the Edge window URL. A browser acceptance walkthrough remains pending. Streamlit remains available.
