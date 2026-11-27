import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { request } from "./api/client";
import { Results, type Row } from "./shared";
import { Button } from "./components/ui/button";

const views = { info: "Model information", registry: "Registry, versions and aliases", runs: "Experiment and run history", metrics: "Evaluation and comparisons", operations: "API operational counters", readiness: "Database readiness", forecasts: "Forecast run history" } as const;
const endpoints: Record<keyof typeof views, string> = { info: "/model/info", registry: "/model/registry", runs: "/model/runs", metrics: "/model/metrics", operations: "/metrics", readiness: "/health/ready", forecasts: "/forecast/runs" };

export default function Models() {
  const [view, setView] = useState<keyof typeof views>("info");
  const [loaded, setLoaded] = useState(false);
  const query = useQuery({ queryKey: ["model", view], queryFn: async ({signal}) => {
    const data = await request<Row | Row[]>(endpoints[view], {signal});
    return Array.isArray(data) ? { forecast_runs: data } : data;
  }, enabled: loaded, staleTime: 0 });
  return <><div className="page-heading"><div><h1>Model Intelligence</h1><p>Registered models and historical MLflow evaluation.</p></div></div><section className="panel filters"><label>View<select value={view} onChange={e => { setLoaded(false); setView(e.target.value as keyof typeof views); }}>{Object.entries(views).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><Button onClick={() => loaded ? void query.refetch() : setLoaded(true)}>Load model details</Button></section>{loaded && (query.isFetching ? <div className="panel loading" role="status">Loading MLflow metadata...</div> : query.isError ? <div className="error" role="alert">{query.error.message}</div> : query.data && <Results data={query.data}/>)}</>;
}
