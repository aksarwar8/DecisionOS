import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { request } from "./api/client";
import { Results, type Row } from "./shared";
import { Button } from "./components/ui/button";

const views = { info: "Model information", registry: "Registry, versions and aliases", runs: "Experiment and run history", metrics: "Evaluation and comparisons" } as const;

export default function Models() {
  const [view, setView] = useState<keyof typeof views>("info");
  const [loaded, setLoaded] = useState(false);
  const query = useQuery({ queryKey: ["model", view], queryFn: ({signal}) => request<Row>("/model/" + view, {signal}), enabled: loaded, staleTime: 0 });
  return <><div className="page-heading"><div><h1>Model Intelligence</h1><p>Registered models and historical MLflow evaluation.</p></div></div><section className="panel filters"><label>View<select value={view} onChange={e => { setLoaded(false); setView(e.target.value as keyof typeof views); }}>{Object.entries(views).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><Button onClick={() => loaded ? void query.refetch() : setLoaded(true)}>Load model details</Button></section>{loaded && (query.isFetching ? <div className="panel loading" role="status">Loading MLflow metadata...</div> : query.isError ? <div className="error" role="alert">{query.error.message}</div> : query.data && <Results data={query.data}/>)}</>;
}
