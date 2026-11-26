# React frontend architecture

`frontend/src/main.tsx` starts the shared TanStack Query client and React Router. It owns the sidebar, header, API liveness indicator and persistent theme. The analytical workspace, forecasting, model views and supporting workspace pages load through lazy route imports.

`api/client.ts` owns URL parameters, JSON requests, cancellation, timeouts and FastAPI validation messages. The Vite development proxy sends `/api` to FastAPI on port 8000. In production, serve the SPA routes and proxy `/api` at the same origin, or configure `VITE_API_BASE_URL` and supply suitable CORS on the API host.

`Analytics.tsx` holds editable filters separately from submitted request parameters. Changing filters clears the submitted parameters so the user cannot mistake a prior response for the new filter selection. TanStack Query keys include the endpoint and submitted parameters. Catalog queries cache for two minutes and search waits 300 ms after typing.

`Forecast.tsx` uses explicit POST actions. Preview precedes batch generation, and backend limits remain authoritative. Forecast response types expose the dates and inputs used for the actual and forecast chart. Hiding an old response also detaches the query from its previous inputs.

`shared.tsx` provides selectors, multiple selection, numeric formatting and tables. `components/AnalysisCharts.tsx` prepares datasets for specific charts. Backend values supply cumulative ABC contribution, growth, coverage and forecast totals. Chart transformations arrange data for display. `components/Chart.tsx` registers only the ECharts modules used by the app and disposes its chart and observers on unmount. Styles combine Tailwind, a shadcn-style button and dashboard CSS.

`reports.tsx` formats the loaded response and its filters as timestamped CSV or Markdown. The CSV preserves numeric zero and quotes formula-like text for spreadsheet use. Analytical payloads still use generic records in the shared table and report renderers. Forecast and catalog controls use concrete interfaces where the fields drive behavior.

The test suite mocks the network for component workflows. Live HTTP requests and browser checks supply separate evidence.

React is the primary interface. The user confirmed that it works in a browser. Streamlit remains a legacy fallback while individual workflows receive detailed acceptance.
