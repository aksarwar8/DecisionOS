import { AnalysisCharts } from "./components/AnalysisCharts"; import { Downloads } from "./reports"; import { CatalogFilter, MultiSelect } from "./shared";
import { useState } from "react"; import { useQuery } from "@tanstack/react-query"; import { BarChart3 } from "lucide-react"; import { request, type Params, ApiError } from "./api/client"; import { Button } from "./components/ui/button"; import { CatalogSelect, Results, titleize, type Row, type Config } from "./shared";
export default function AnalyticsPage({ config, pathname }: { config: Config; pathname: string }) {
  const [days, setDays] = useState("30"); const [end, setEnd] = useState(""); const [product, setProduct] = useState(""); const [store, setStore] = useState("");
  const [state,setState]=useState(""); const [category,setCategory]=useState(""); const [department,setDepartment]=useState(""); const [ids,setIds]=useState<number[]>([]);
  const [aggregation,setAggregation]=useState("weekly"); const [metric,setMetric]=useState("total_demand");
  const [eventType,setEventType]=useState(""); const [eventName,setEventName]=useState(""); const [before,setBefore]=useState("3"); const [after,setAfter]=useState("3");
  const [subset,setSubset]=useState(""); const [offset,setOffset]=useState(0); const [minimum,setMinimum]=useState("30");
  const [variant, setVariant] = useState("default");
  const [params, setParams] = useState<Params | null>(null);
  const variants: Record<string, Record<string, { path: string; options?: Params; product?: boolean; store?: boolean }>> = {
    "/products": {
      default: { path: "/analytics/product-rankings", options: { sort: "top", limit: 20 } },
      bottom: { path: "/analytics/product-rankings", options: { sort: "bottom", limit: 20 } },
      growth: { path: "/analytics/product-rankings", options: { sort: "growth", limit: 20 } },
      decline: { path: "/analytics/product-rankings", options: { sort: "decline", limit: 20 } },
      variability: { path: "/analytics/product-rankings", options: { sort: "variability", limit: 20 } },
      zero_frequency: { path: "/analytics/product-rankings", options: { sort: "zero_frequency", limit: 20 } },
      comparison: {path:"/analytics/product-comparison"}, segments: { path: "/analytics/demand-segments" }, abc: { path: "/analytics/abc-analysis" },
      performance: { path: "/analytics/product-performance", product: true },
    },
    "/stores": {
      default: { path: "/analytics/store-rankings" }, growth: { path: "/analytics/store-rankings", options: { sort: "growth" } },
      comparison: {path:"/analytics/store-comparison"}, bottom: {path:"/analytics/store-rankings",options:{sort:"bottom"}}, decline:{path:"/analytics/store-rankings",options:{sort:"decline"}}, average:{path:"/analytics/store-rankings",options:{sort:"average"}}, state: { path: "/analytics/state-performance" }, category: { path: "/analytics/category-performance" },
      department: { path: "/analytics/category-performance", options: { group_by: "department" } },
      store_category: { path: "/analytics/demand-matrix", options: { dimensions: "store_category" } },
      store_department: { path: "/analytics/demand-matrix", options: { dimensions: "store_department" } },
      state_category: { path: "/analytics/demand-matrix", options: { dimensions: "state_category" } },
      performance: { path: "/analytics/store-performance", store: true },
    },
    "/seasonality": {
      default: { path: "/analytics/seasonality", options: { group_by: "weekday" } },
      month: { path: "/analytics/seasonality", options: { group_by: "month" } },
      year: { path: "/analytics/seasonality", options: { group_by: "year" } },
      year_month: { path: "/analytics/seasonality", options: { group_by: "year_month" } },
      weekday_weekend: { path: "/analytics/seasonality", options: { group_by: "weekday_weekend" } },
      event_catalog:{path:"/analytics/event-catalog"}, event_window:{path:"/analytics/event-window"}, events: { path: "/analytics/event-analysis" }, snap: { path: "/analytics/snap-analysis" },
    },
  };
  const choices = variants[pathname];
  const selected = choices?.[variant] ?? { path: config.path, options: config.options, product: config.product, store: config.store };
  const compare = variant === "comparison"; const calendar = pathname === "/seasonality"; const events = variant === "events" || variant === "event_window";
  const catalog = useQuery({queryKey:["event-catalog"],queryFn:({signal})=>request<{events:{name:string;event_type:string|null}[]}>("/analytics/event-catalog",{signal}),enabled:events,staleTime:120000});
  const useAggregation = ["/analytics/sales-report","/analytics/product-comparison","/analytics/product-performance","/analytics/store-comparison","/analytics/store-performance","/analytics/state-performance","/analytics/category-performance","/analytics/snap-analysis"].includes(selected.path);
  const productFilter = selected.product || calendar && variant !== "event_catalog" || pathname === "/sales" || variant === "segments";
  const storeFilter = variant !== "event_catalog" && !(pathname === "/stores" && compare);
  const paginated = pathname === "/products" && !compare && variant !== "performance";
  const query = useQuery({ queryKey: ["analysis", selected.path, params], queryFn: ({ signal }) => request<Row>(selected.path, { params: params ?? {}, signal }), enabled: params !== null, refetchOnReconnect:false, retry: false, staleTime: 0 });
  const changed = () => {setParams(null); setOffset(0);};
  return <><div className="page-heading"><div><div className="eyebrow">DECISIONOS / ANALYTICS</div><h1>{config.title}</h1><p>{config.description}</p></div><span className="history-badge">Historical M5 data</span></div><section className="panel filter-panel"><div className="panel-heading"><div><h2>Analysis settings</h2><p>Select a period, then load the report.</p></div></div><div className="filters">{choices && <label>Analysis<select value={variant} onChange={(e) => { setVariant(e.target.value); setSubset(""); setIds([]); setDays("30"); changed(); }}>{Object.keys(choices).map((v) => <option value={v} key={v}>{v === "default" ? "Overview" : titleize(v)}</option>)}</select></label>}<label>Period<select value={days} onChange={(e) => { setDays(e.target.value); changed(); }}>{[30, 60, 90, 180, 365, ...(selected.path.endsWith("/seasonality") && product && store ? [730,1095] : [])].map((n) => <option key={n} value={n}>{n} days</option>)}</select></label><label>Historical end date<input type="date" value={end} onChange={(e) => { setEnd(e.target.value); changed(); }}/></label>{variant !== "event_catalog" && <>
<CatalogFilter kind="state" value={state} onChange={v=>{setState(v);setStore("");setIds([]);setDays("30");changed();}}/>
<CatalogFilter kind="category" value={category} onChange={v=>{setCategory(v);setDepartment("");setProduct("");setIds([]);setDays("30");changed();}}/>
<CatalogFilter kind="department" category={category} value={department} onChange={v=>{setDepartment(v);setProduct("");setIds([]);setDays("30");changed();}}/>
{productFilter && <CatalogSelect key={category+":"+department} product category={category} department={department} value={product} onChange={v=>{setProduct(v);setDays("30");changed();}}/>}
{storeFilter && <CatalogSelect state={state} value={store} onChange={v=>{setStore(v);setDays("30");changed();}}/>}
{compare && <MultiSelect product={pathname==="/products"} values={ids} onChange={v=>{setIds(v);changed();}} category={category} department={department} state={state}/>}
{useAggregation && <label>Aggregation<select value={aggregation} onChange={e=>{setAggregation(e.target.value);changed();}}>{["daily","weekly","monthly"].map(v=><option key={v}>{v}</option>)}</select></label>}
{events && <><label>Event type<select value={eventType} onChange={e=>{setEventType(e.target.value);setEventName("");changed();}}><option value="">All types</option>{[...new Set(catalog.data?.events.flatMap(r=>r.event_type?[r.event_type]:[])??[])].map(v=><option key={v}>{v}</option>)}</select></label><label>Event name<select value={eventName} onChange={e=>{setEventName(e.target.value);changed();}}><option value="">All events</option>{[...new Set(catalog.data?.events.filter(r=>!eventType||r.event_type===eventType).map(r=>r.name)??[])].map(v=><option key={v}>{v}</option>)}</select></label>{catalog.isError && <small>Event catalog unavailable</small>}</>}
{variant === "event_window" && <>{[[before,setBefore,"Days before"],[after,setAfter,"Days after"]].map(([value,set,label])=><label key={String(label)}>{String(label)}<select value={String(value)} onChange={e=>{(set as (v:string)=>void)(e.target.value);changed();}}>{Array.from({length:8},(_,i)=><option key={i}>{i}</option>)}</select></label>)}</>}
{selected.path.endsWith("demand-matrix") && <label>Heatmap metric<select value={metric} onChange={e=>setMetric(e.target.value)}>{["total_demand","contribution_pct","percentage_growth"].map(v=><option value={v} key={v}>{titleize(v)}</option>)}</select></label>}
{(variant==="abc" || variant==="segments") && <label>{variant==="abc"?"ABC classification":"Demand segment"}<select value={subset} onChange={e=>{setSubset(e.target.value);changed();}}><option value="">All</option>{(variant==="abc"?["A","B","C","Unclassified"]:["Zero average","Low demand","Medium demand","High demand"]).map(value=><option key={value}>{value}</option>)}</select></label>}
{pathname==="/products" && ["growth","decline"].includes(variant) && <label>Minimum previous demand<input type="number" min="1" value={minimum} onChange={e=>{setMinimum(e.target.value);changed();}}/></label>}
</>}
<Button disabled={query.isFetching || Boolean(selected.product && !product || selected.store && !store || compare && !ids.length || variant==="event_window" && !eventName && !eventType)} onClick={()=>{
const next:Params = variant==="event_catalog"?{}:{...selected.options,days,end_date:end, state,category,department, product_id:productFilter?product:undefined,store_id:storeFilter?store:undefined,aggregation:useAggregation?aggregation:undefined,
...(variant==="abc"?{classification:subset}:variant==="segments"?{segment:subset}:{}),...(compare?{[pathname==="/products"?"product_ids":"store_ids"]:ids}:{}),...(events?{event_type:eventType,event_name:eventName}:{}),...(variant==="event_window"?{before,after}:{}),...(paginated?{offset,limit:Math.min(100,variant==="abc"?100:20)}:{}),...(pathname==="/products" && ["growth","decline"].includes(variant)?{minimum_previous_demand:minimum}:{})};
if(params && JSON.stringify(params)===JSON.stringify(next)) void query.refetch(); else setParams(next);
}}>Load analysis</Button></div></section>{query.isFetching && <div className="panel loading" role="status">Loading historical analysis…</div>}{query.isError && <div className="error" role="alert">{query.error instanceof ApiError ? `${query.error.message}${query.error.requestId ? ` · Request ${query.error.requestId}` : ""}` : "The API could not be reached."}</div>}{params && query.data && !query.isFetching && !query.isError && <><AnalysisCharts data={query.data} path={selected.path} metric={metric}/><Results key={JSON.stringify(params)} data={query.data}/><Downloads title={config.title+" - "+titleize(variant)} data={query.data} filters={params} assumptions="M5 demand is measured in units. Null values indicate missing observations or undefined metrics. Calendar and price associations are descriptive. Matrix contribution is within each geography. Window average demand uses calendar days; observed-day metrics use days with records. Zero-demand frequency uses observed days. Price weighting uses matched sales units; no currency is specified."/>
{paginated && <div className="pagination"><Button variant="outline" disabled={!offset} onClick={()=>{const next=Math.max(0,offset-Number(params.limit));setOffset(next);setParams({...params,offset:next});}}>Previous results</Button><Button variant="outline" disabled={offset+Number(params.limit)>=Number(query.data.total)} onClick={()=>{const next=offset+Number(params.limit);setOffset(next);setParams({...params,offset:next});}}>Next results</Button></div>}</>}{!params && <div className="empty"><BarChart3 size={28}/><h2>Ready to explore</h2><p>Choose your settings and load a report to view historical results.</p></div>}</>;
}
