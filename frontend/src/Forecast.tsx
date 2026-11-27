import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { request } from "./api/client";
import { Button } from "./components/ui/button";
import { CatalogSelect, CatalogFilter, MultiSelect, Results, type Row } from "./shared";
import { Downloads } from "./reports";
import { Chart } from "./components/Chart";

const scopes = { individual: "Individual forecast", pair: "Single pair with history", product: "One product across stores", pairs: "Explicit pairs", store: "Store", state: "State", category: "Category", department: "Department", business: "Entire business preview" } as const;
type Scope = keyof typeof scopes;
type Pair = {product_id: number; store_id: number};
type Preview = Row & {candidate_pairs: number; estimated_rows: number; max_pairs: number; max_rows: number; within_limits: boolean};
type Interval = {method:string; forecast_origin:string; coverage:number; calibration_count:number; limitation:string; forecasts:{date:string;prediction:number;lower:number;upper:number}[]};
type SavedRun = {run_id:string;status:string;created_at:string;completed_pairs:number;total_pairs:number|null;error?:string;result?:Batch};
type Batch = Preview & {origin: string; forecast_start: string; forecast_end: string; coverage: "complete" | "partial"; historical: {date: string; demand: number}[]; daily: {date: string; prediction: number}[]};

export default function Forecast() {
  const [batchSize,setBatchSize]=useState("50"); const [method,setMethod]=useState("hybrid"); const [coverage,setCoverage]=useState("0.8"); const [runId,setRunId]=useState("");
  const [scope, setScope] = useState<Scope>("individual");
  const [product, setProduct] = useState(""); const [store, setStore] = useState("");
  const [stores, setStores] = useState<number[]>([]);
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [filter, setFilter] = useState(""); const [horizon, setHorizon] = useState("7"); const [origin, setOrigin] = useState("");
  const [action, setAction] = useState<{path: string; body: object; sequence: number} | null>(null);
  const [approved, setApproved] = useState(false);
  const clear = () => { setAction(null); setApproved(false); setRunId(""); };
  const single = scope === "individual";
  const valid = scope === "business" || (scope === "pairs" ? pairs.length > 0 : scope === "product" ? !!product && stores.length > 0 : scope === "pair" || single ? !!product && !!store : scope === "store" ? !!store : !!filter);
  const body = single ? { product_id: Number(product), store_id: Number(store), horizon: Number(horizon), method } : {
    scope, horizon: Number(horizon), method, batch_size:Number(batchSize), origin: origin || undefined,
    product_ids: scope === "pair" || scope === "product" ? [Number(product)] : undefined,
    store_ids: scope === "pair" || scope === "store" ? [Number(store)] : scope === "product" ? stores : undefined,
    pairs: scope === "pairs" ? pairs : undefined,
    ...(["state", "category", "department"].includes(scope) ? {[scope]: filter} : {}),
  };
  const run = (path: string) => { setRunId(""); setAction({path, body: path.endsWith("/intervals") ? {...body,coverage:Number(coverage)} : body, sequence: Date.now()}); };
  const query = useQuery({queryKey: ["forecast", action], enabled: !!action, queryFn: ({signal}) => request<Row>(action!.path, {method:"POST", body: action!.body, signal, timeout: single ? 120000 : 30000}), refetchOnReconnect: false, gcTime: 0});
  const preview = action?.path.endsWith("scope-preview") ? query.data as Preview | undefined : undefined;
  const batch = action?.path.endsWith("/runs") ? (query.data as unknown as SavedRun | undefined)?.result : undefined;
  const interval = action?.path.endsWith("/intervals") ? query.data as unknown as Interval | undefined : undefined;
  const saved = useQuery({queryKey:["forecast-runs"],queryFn:({signal})=>request<SavedRun[]>("/forecast/runs",{signal}),enabled:!single,staleTime:30000});
  const previous = useQuery({queryKey:["forecast-run",runId],queryFn:({signal})=>request<SavedRun>("/forecast/runs/"+runId,{signal}),enabled:!!runId,refetchInterval:query=>query.state.data?.status === "running" ? 5000 : false});
  const displayedBatch = batch ?? previous.data?.result;
  const currentPair = {product_id: Number(product), store_id: Number(store)};
  const addDisabled = !product || !store || pairs.length >= 100 || pairs.some(p => p.product_id === currentPair.product_id && p.store_id === currentPair.store_id);
  return <><div className="page-heading"><div><h1>Demand Forecasting</h1><p>Forecast demand for individual items or aggregate eligible pairs.</p></div></div>
    <section className="panel filters">
      <label>Scope<select value={scope} onChange={e => {setScope(e.target.value as Scope); setFilter(""); clear();}}>{Object.entries(scopes).map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></label>
      {["individual","pair","product","pairs"].includes(scope) && <CatalogSelect product value={product} onChange={v => {setProduct(v); clear();}}/>}
      {["individual","pair","store","pairs"].includes(scope) && <CatalogSelect value={store} onChange={v => {setStore(v); clear();}}/>}
      {scope === "product" && <MultiSelect values={stores} onChange={ids => {setStores(ids); clear();}} max={10}/>}
      {scope === "pairs" && <div><Button disabled={addDisabled} onClick={() => {setPairs([...pairs,currentPair]); clear();}}>Add pair</Button><p>{pairs.length} pairs selected</p><Button variant="outline" disabled={!pairs.length} onClick={() => {setPairs([]); clear();}}>Clear pairs</Button></div>}
      {(scope === "state" || scope === "category" || scope === "department") && <CatalogFilter kind={scope} value={filter} onChange={v => {setFilter(v); clear();}}/>}
      {!single && <label>Batch size<select value={batchSize} onChange={e=>{setBatchSize(e.target.value);clear();}}>{[1,5,10,25,50,100].map(n=><option key={n} value={n}>{n} pairs</option>)}</select></label>}
      {!single && <label>Forecast origin<input type="date" value={origin} onChange={e => {setOrigin(e.target.value); clear();}}/></label>}
      <label>Method<select value={method} onChange={e=>{setMethod(e.target.value);clear();setRunId("");}}><option value="hybrid">Registered hybrid (established)</option><option value="tsb">TSB (experimental)</option><option value="moving_average">Moving average (experimental)</option><option value="seasonal_naive">Seasonal naive (experimental)</option></select></label><label>Horizon<select value={horizon} onChange={e => {setHorizon(e.target.value); clear();}}>{[7,14,28].map(n => <option key={n} value={n}>{n} days</option>)}</select></label>
      <Button disabled={!valid || query.isFetching} onClick={() => {setApproved(false); run(single ? "/forecast/" : "/forecast/scope-preview");}}>{single ? "Generate forecast" : "Preview workload"}</Button>
      {!single && scope !== "business" && <Button disabled={query.isFetching || !(preview?.within_limits && preview.candidate_pairs > 0 || approved)} onClick={() => {setApproved(true); run("/forecast/runs");}}>Generate batch forecast</Button>}
      {single && <><label>Interval coverage<select value={coverage} onChange={e=>{setCoverage(e.target.value);clear();}}><option value="0.8">80%</option><option value="0.95">95%</option></select></label><Button variant="outline" disabled={!valid||query.isFetching} onClick={()=>run("/forecast/intervals")}>Estimate interval</Button></>}
    </section>
    {!single && <section className="panel"><h2>Saved forecast runs</h2><label>Run<select value={runId} onChange={e=>{setAction(null);setRunId(e.target.value);}}><option value="">Select a saved run</option>{Array.isArray(saved.data) && saved.data.map(run=><option key={run.run_id} value={run.run_id}>{run.created_at} · {run.status} · {run.run_id.slice(0,8)}</option>)}</select></label><Button variant="outline" onClick={()=>void saved.refetch()}>Refresh runs</Button>{saved.isError&&<p>Saved runs are unavailable.</p>}{previous.isFetching&&<p>Loading saved run...</p>}{previous.isError&&<p>Could not load this run.</p>}{previous.data && previous.data.status !== "completed" && <p>Run status: {previous.data.status} · {previous.data.completed_pairs} of {previous.data.total_pairs ?? "?"} pairs processed. {previous.data.error}</p>}</section>}
    {scope === "business" && <p>Entire business is preview-only. Use a smaller scope to generate predictions.</p>}
    {query.isFetching && <div className="panel loading" role="status">Processing forecast request...</div>}
    {action && query.isError && <div className="error" role="alert">{query.error.message}</div>}
    {preview && !preview.within_limits && <div className="error">Workload exceeds the synchronous limit of {preview.max_pairs} pairs or {preview.max_rows} prediction rows.</div>}
    {displayedBatch && <section className="panel"><h2>Historical and predicted demand</h2><p>Forecast origin {displayedBatch.origin}. Coverage {displayedBatch.coverage}.</p><Chart option={{tooltip:{trigger:"axis"},legend:{},xAxis:{type:"category",data:[...displayedBatch.historical,...displayedBatch.daily].map(d=>d.date)},yAxis:{type:"value",name:"Units"},series:[{name:"Actual",type:"line",data:[...displayedBatch.historical.map(d=>d.demand),...displayedBatch.daily.map(()=>null)],markLine:{data:[{xAxis:displayedBatch.origin}]}},{name:"Forecast",type:"line",lineStyle:{type:"dashed"},data:[...displayedBatch.historical.map(()=>null),...displayedBatch.daily.map(d=>d.prediction)]}]}}/></section>}
    {interval && <section className="panel"><h2>Empirical prediction interval</h2><p>{interval.coverage*100}% nominal coverage · {interval.calibration_count} historical calibration origins. {interval.limitation}</p><Chart option={{tooltip:{trigger:"axis"},legend:{},xAxis:{type:"category",data:interval.forecasts.map(r=>r.date)},yAxis:{type:"value",name:"Units"},series:[{name:"Lower bound",type:"line",stack:"interval",symbol:"none",lineStyle:{opacity:0},data:interval.forecasts.map(r=>r.lower)},{name:"Interval",type:"line",stack:"interval",symbol:"none",lineStyle:{opacity:0},areaStyle:{opacity:0.2},data:interval.forecasts.map(r=>r.upper-r.lower)},{name:"Prediction",type:"line",data:interval.forecasts.map(r=>r.prediction)}]}}/></section>}
    {previous.data?.result && <><Results data={previous.data.result}/><Downloads title="Saved forecast" data={previous.data.result} filters={previous.data} assumptions="Saved forecast run. Coverage and exclusions are shown in the result."/></>}
    {action && query.data && !query.isFetching && <><Results data={query.data}/><Downloads title="Demand forecast" data={query.data} filters={action.body} assumptions="Historical demand covers eligible pairs. Forecasts are point predictions in units."/></>}
  </>;
}
