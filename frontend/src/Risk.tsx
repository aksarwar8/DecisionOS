import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { request } from "./api/client";
import { Button } from "./components/ui/button";
import { CatalogSelect, Results, type Row } from "./shared";
import { Downloads } from "./reports";

export default function Risk() {
  const [product,setProduct]=useState("");
  const [store,setStore]=useState("");
  const [view,setView]=useState("demand");
  const [severity,setSeverity]=useState("all");
  const [params,setParams]=useState<{product_id?:number;store_id:number;severity:string}|null>(null);
  const query=useQuery({queryKey:["risk",view,params],enabled:!!params,retry:false,
    queryFn:({signal})=>request<Row>("/risk/"+view,{params:params ?? {},signal})});
  function clear(){setParams(null);}
  return <><div className="page-heading"><div><h1>Anomaly &amp; Risk Intelligence</h1><p>Investigate historical demand signals for a selected product and store.</p></div></div>
    <section className="panel filters"><label>Signal<select value={view} onChange={e=>{setView(e.target.value);clear();}}><option value="demand">Demand</option><option value="price">Price changes</option><option value="store">Store demand</option></select></label>{view !== "store" && <CatalogSelect product value={product} onChange={v=>{setProduct(v);clear();}}/>}
    <CatalogSelect value={store} onChange={v=>{setStore(v);clear();}}/>
    <label>Severity<select value={severity} onChange={e=>{setSeverity(e.target.value);clear();}}><option value="all">All</option><option value="medium">Medium</option><option value="high">High</option></select></label>
    <Button disabled={(!product && view !== "store")||!store||query.isFetching} onClick={()=>setParams({...(view !== "store" ? {product_id:Number(product)} : {}),store_id:Number(store),severity})}>Load signals</Button></section>
    {params && query.isFetching && <div className="panel loading" role="status">Analyzing historical demand...</div>}
    {params && query.isError && <div className="error" role="alert">{query.error.message}</div>}
    {params && query.data && !query.isFetching && <><Results data={query.data}/><Downloads title="Demand risk signals" data={query.data} filters={params} assumptions="Statistical signals do not establish stockouts or fraud."/></>}
  </>;
}
