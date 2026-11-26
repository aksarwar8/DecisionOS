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
type Batch = Preview & {origin: string; forecast_start: string; forecast_end: string; coverage: "complete" | "partial"; historical: {date: string; demand: number}[]; daily: {date: string; prediction: number}[]};

export default function Forecast() {
  const [scope, setScope] = useState<Scope>("individual");
  const [product, setProduct] = useState(""); const [store, setStore] = useState("");
  const [stores, setStores] = useState<number[]>([]);
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [filter, setFilter] = useState(""); const [horizon, setHorizon] = useState("7"); const [origin, setOrigin] = useState("");
  const [action, setAction] = useState<{path: string; body: object; sequence: number} | null>(null);
  const [approved, setApproved] = useState(false);
  const clear = () => { setAction(null); setApproved(false); };
  const single = scope === "individual";
  const valid = scope === "business" || (scope === "pairs" ? pairs.length > 0 : scope === "product" ? !!product && stores.length > 0 : scope === "pair" || single ? !!product && !!store : scope === "store" ? !!store : !!filter);
  const body = single ? { product_id: Number(product), store_id: Number(store), horizon: Number(horizon) } : {
    scope, horizon: Number(horizon), origin: origin || undefined,
    product_ids: scope === "pair" || scope === "product" ? [Number(product)] : undefined,
    store_ids: scope === "pair" || scope === "store" ? [Number(store)] : scope === "product" ? stores : undefined,
    pairs: scope === "pairs" ? pairs : undefined,
    ...(["state", "category", "department"].includes(scope) ? {[scope]: filter} : {}),
  };
  const run = (path: string) => setAction({path, body, sequence: Date.now()});
  const query = useQuery({queryKey: ["forecast", action], enabled: !!action, queryFn: ({signal}) => request<Row>(action!.path, {method:"POST", body: action!.body, signal, timeout: single ? 120000 : 30000}), refetchOnReconnect: false, gcTime: 0});
  const preview = action?.path.endsWith("scope-preview") ? query.data as Preview | undefined : undefined;
  const batch = action?.path.endsWith("/batch") ? query.data as Batch | undefined : undefined;
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
      {!single && <label>Forecast origin<input type="date" value={origin} onChange={e => {setOrigin(e.target.value); clear();}}/></label>}
      <label>Horizon<select value={horizon} onChange={e => {setHorizon(e.target.value); clear();}}>{[7,14,28].map(n => <option key={n} value={n}>{n} days</option>)}</select></label>
      <Button disabled={!valid || query.isFetching} onClick={() => {setApproved(false); run(single ? "/forecast/" : "/forecast/scope-preview");}}>{single ? "Generate forecast" : "Preview workload"}</Button>
      {!single && scope !== "business" && <Button disabled={query.isFetching || !(preview?.within_limits && preview.candidate_pairs > 0 || approved)} onClick={() => {setApproved(true); run("/forecast/batch");}}>Generate batch forecast</Button>}
    </section>
    {scope === "business" && <p>Entire business is preview-only. Use a smaller scope to generate predictions.</p>}
    {query.isFetching && <div className="panel loading" role="status">Processing forecast request...</div>}
    {action && query.isError && <div className="error" role="alert">{query.error.message}</div>}
    {preview && !preview.within_limits && <div className="error">Workload exceeds the synchronous limit of {preview.max_pairs} pairs or {preview.max_rows} prediction rows.</div>}
    {batch && <section className="panel"><h2>Historical and predicted demand</h2><p>Forecast origin {batch.origin}. Coverage {batch.coverage}.</p><Chart option={{tooltip:{trigger:"axis"},legend:{},xAxis:{type:"category",data:[...batch.historical,...batch.daily].map(d=>d.date)},yAxis:{type:"value",name:"Units"},series:[{name:"Actual",type:"line",data:[...batch.historical.map(d=>d.demand),...batch.daily.map(()=>null)],markLine:{data:[{xAxis:batch.origin}]}},{name:"Forecast",type:"line",lineStyle:{type:"dashed"},data:[...batch.historical.map(()=>null),...batch.daily.map(d=>d.prediction)]}]}}/></section>}
    {action && query.data && !query.isFetching && <><Results data={query.data}/><Downloads title="Demand forecast" data={query.data} filters={action.body} assumptions="Historical demand covers eligible pairs. Forecasts are point predictions in units."/></>}
  </>;
}
