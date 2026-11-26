import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { request } from "./api/client";
import { Button } from "./components/ui/button";
import { CatalogSelect, Results, type Row } from "./shared";
import { Downloads } from "./reports";

export default function Workspace({view}: {view:"system"|"reports"|"history"}) {
  const [product,setProduct]=useState("");
  const [store,setStore]=useState("");
  const [days,setDays]=useState("90");
  const [job,setJob]=useState<{product_id:number;store_id:number;days:number}|null>(null);
  const system=useQuery({queryKey:["capabilities"],queryFn:({signal})=>request<Row>("/analytics/capabilities",{signal}),enabled:view==="system",staleTime:120000});
  const health=useQuery({queryKey:["health"],queryFn:({signal})=>request<{status:string}>("/health",{signal}),enabled:view==="system",staleTime:60000});
  const history=useQuery({queryKey:["legacy-history",job],enabled:view==="history"&&!!job,queryFn:async({signal})=>{
    if(!job) throw new Error("Select a product and store.");
    const {product_id,store_id,days}=job;
    const product=await request<Row>("/analytics/products/"+product_id,{params:{days},signal});
    const store=await request<Row>("/analytics/stores/"+store_id,{params:{days},signal});
    const trend=await request<Row>("/analytics/trends",{params:job,signal});
    return {product,store,trend};
  }});
  if(view==="system") return <><div className="page-heading"><div><h1>System Status</h1><p>API liveness and available analytics capabilities.</p></div></div><Results data={{api_liveness:health.data?.status??(health.isPending?"Checking":"Unavailable"),frontend_version:"1.0.0"}}/><p>Liveness checks the API process. Analytics capabilities are reported separately.</p>{system.data&&<Results data={system.data}/ >}{system.isError&&<div className="error">{system.error.message}</div>}</>;
  if(view==="reports") return <><div className="page-heading"><div><h1>Business Reports</h1><p>Load an analysis and download its results as CSV or Markdown from the same page.</p></div></div><section className="panel report-links">{[["/","Executive Overview"],["/sales","Sales Intelligence"],["/products","Product Intelligence"],["/stores","Store & Category"],["/seasonality","Seasonality & Events"],["/price","Price Intelligence"],["/forecast","Demand Forecasting"]].map(([path,title])=><Link key={path} to={path}>{title}</Link>)}</section></>;
  return <><div className="page-heading"><div><h1>Product–Store History</h1><p>Inspect product-wide, store-wide and pair-level demand.</p></div></div><section className="panel filters"><CatalogSelect product value={product} onChange={v=>{setProduct(v);setJob(null);}}/><CatalogSelect value={store} onChange={v=>{setStore(v);setJob(null);}}/><label>Historical period<select value={days} onChange={e=>{setDays(e.target.value);setJob(null);}}>{[30,60,90,180,365].map(n=><option key={n} value={n}>{n} days</option>)}</select></label><Button disabled={!product||!store||history.isFetching} onClick={()=>job?void history.refetch():setJob({product_id:Number(product),store_id:Number(store),days:Number(days)})}>Load history</Button></section>{history.isFetching&&<div className="panel loading">Loading historical demand...</div>}{job&&history.isError&&<div className="error">{history.error.message}</div>}{job&&history.data&&!history.isFetching&&!history.isError&&<><Results data={history.data}/><Downloads title="Product–Store History" data={history.data} filters={job} assumptions="Product and store reports use the platform date anchor. Pair trends use the latest date observed for the selected pair."/></>}</>;
}
