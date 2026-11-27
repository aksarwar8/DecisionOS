import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { request } from "./api/client";
import { Button } from "./components/ui/button";
import { CatalogSelect, Results, type Row } from "./shared";
import { Downloads } from "./reports";
import { Chart } from "./components/Chart";

type Inventory = {stock:number;incoming:number;lead_days:number;safety_stock:number;minimum_order:number;
  order_multiple:number;service_level:number;unit_cost:number;holding_cost:number;shortage_cost:number;fixed_order:number;simulation_budget:number};
type SavedRun = {run_id:string;status:string;created_at:string;request:{scope:string;horizon:number}};
type Decision = Row & {projection:{date:string;stock:number;demand:number}[]};
const defaults:Inventory={stock:20,incoming:0,lead_days:7,safety_stock:10,minimum_order:1,order_multiple:1,
  service_level:0.95,unit_cost:1,holding_cost:0.01,shortage_cost:2,fixed_order:25,simulation_budget:500};
const labels:Record<keyof Inventory,string>={stock:"Current stock",incoming:"Incoming inventory",lead_days:"Lead time (days)",
 safety_stock:"Safety stock (units)",minimum_order:"Minimum order",order_multiple:"Order multiple",service_level:"Target service level",
 unit_cost:"Unit procurement cost",holding_cost:"Daily holding cost per unit",shortage_cost:"Shortage cost per unit",
 fixed_order:"Fixed order quantity",simulation_budget:"Simulation budget"};

export default function Prescriptive(){
 const [tab,setTab]=useState("recommendation"); const [seed,setSeed]=useState(42);
 const [runId,setRunId]=useState(""); const [runIds,setRunIds]=useState<string[]>([]); const [budget,setBudget]=useState(500); const [leadDelta,setLeadDelta]=useState(0); const [costFactor,setCostFactor]=useState(1); const [holdingFactor,setHoldingFactor]=useState(1); const [serviceLevel,setServiceLevel]=useState(0.95); const [product,setProduct]=useState("");const [store,setStore]=useState("");
 const [inputs,setInputs]=useState<Inventory>(defaults); const [demand,setDemand]=useState(1); const [stock,setStock]=useState(1);
 const [result,setResult]=useState<Row|null>(null); const [error,setError]=useState("");const [loading,setLoading]=useState(false);
 const [review,setReview]=useState(""); const generation=useRef(0);
 const history=useQuery({queryKey:["decision-reviews"],queryFn:({signal})=>request<Row[]>("/prescriptive/reviews",{signal}),enabled:tab==="history",staleTime:0});
 const runs=useQuery({queryKey:["decision-runs"],queryFn:({signal})=>request<SavedRun[]>("/forecast/runs",{signal}),staleTime:30000});
 const clear=()=>{generation.current++;setResult(null);setError("");setReview("");setLoading(false);};
 const call=async()=>{
   clear();const current=generation.current;setLoading(true);
   try{
     const body=tab==="allocation"?{items:runIds.map(id=>({run_id:id,assumptions:inputs})),budget}:tab==="simulation"?{product_id:Number(product),store_id:Number(store),assumptions:inputs}:
       tab==="scenario"?{run_id:runId,assumptions:inputs,demand_multiplier:demand,stock_multiplier:stock,lead_days_delta:leadDelta,unit_cost_multiplier:costFactor,holding_cost_multiplier:holdingFactor,service_level:serviceLevel,budget}:
       {run_id:runId,assumptions:inputs};
     const value=await request<Row>("/prescriptive/"+tab,{method:"POST",body,timeout:30000});
     if(current===generation.current)setResult(value);
   }catch(e){if(current===generation.current)setError(e instanceof Error?e.message:"Request failed");}finally{if(current===generation.current)setLoading(false);}
 };
 const generate=async()=>{
   clear();const current=generation.current;
   try { const value=await request<Inventory>("/prescriptive/assumptions",{params:{product_id:Number(product),store_id:Number(store),seed}}); if(current===generation.current)setInputs(value); }
   catch(e){if(current===generation.current)setError(e instanceof Error?e.message:"Could not generate assumptions");}
 };
 const inventory=async(write:boolean)=>{
   clear();const current=generation.current;
   try {
     const path="/prescriptive/inventory/"+product+"/"+store;
     const record=await request<{assumptions:Inventory}>(path,write ? {method:"PUT",body:inputs} : {});
     if(current!==generation.current)return;
     if(!write) setInputs(record.assumptions);
     setReview(write?"Simulated inventory saved.":"Simulated inventory loaded.");
   } catch(e){if(current===generation.current)setError(e instanceof Error?e.message:"Inventory record unavailable");}
 };
 const save=async(status:string)=>{
   if(!result)return;
   try{await request("/prescriptive/reviews",{method:"POST",body:{decision:result,status}});setReview("Simulated review saved.");}
   catch(e){setError(e instanceof Error?e.message:"Could not save review");}
 };
 const decision=tab==="recommendation"?result as Decision|null:null;
 const comparison=tab==="scenario" && result ? result as {baseline:{recommended_quantity:number;projected_shortage:number};scenario:{recommended_quantity:number;projected_shortage:number}} : null;
 return <><div className="page-heading"><div><h1>Inventory &amp; Decisions</h1><p>Evaluate replenishment scenarios with simulated inventory and costs.</p></div><span className="history-badge">Simulated inventory</span></div>
 <section className="panel"><p><strong>Simulation.</strong> Inventory balances, lead times and costs are assumptions. Results do not represent actual inventory or purchases.</p></section>
 <section className="panel filters"><label>Analysis<select value={tab} onChange={e=>{setTab(e.target.value);clear();}}><option value="recommendation">Replenishment recommendation</option><option value="scenario">What-if scenario</option><option value="simulation">Historical policy simulation</option><option value="allocation">Budget allocation</option><option value="history">Decision review history</option></select></label>
 {tab==="allocation" ? <><label>Forecast runs<select multiple value={runIds} onChange={e=>{setRunIds(Array.from(e.target.selectedOptions,o=>o.value));clear();}}>{runs.data?.filter(r=>r.status==="completed" && r.request.scope==="pair" && r.request.horizon===28).map(r=><option value={r.run_id} key={r.run_id}>{r.created_at} · {r.run_id.slice(0,8)}</option>)}</select></label><label>Budget<input type="number" min="0" value={budget} onChange={e=>{setBudget(Number(e.target.value));clear();}}/></label></> : tab==="history" ? null : tab!=="simulation" ? <label>Saved single-pair 28-day forecast<select value={runId} onChange={e=>{setRunId(e.target.value);clear();}}><option value="">Select forecast run</option>{runs.data?.filter(r=>r.status==="completed" && (r.request.scope==="pair"||r.request.scope==="pairs") && r.request.horizon===28).map(r=><option value={r.run_id} key={r.run_id}>{r.created_at} · {r.run_id.slice(0,8)}</option>)}</select></label> : <><CatalogSelect product value={product} onChange={v=>{setProduct(v);clear();}}/><CatalogSelect value={store} onChange={v=>{setStore(v);clear();}}/></>}
 {tab==="simulation" && <><label>Simulation seed<input type="number" value={seed} onChange={e=>{setSeed(Number(e.target.value));clear();}}/></label><Button variant="outline" disabled={!product||!store} onClick={()=>void generate()}>Generate assumptions</Button><Button variant="outline" disabled={!product||!store} onClick={()=>void inventory(true)}>Save simulated inventory</Button><Button variant="outline" disabled={!product||!store} onClick={()=>void inventory(false)}>Load simulated inventory</Button></>}
 {tab!=="history" && Object.entries(labels).map(([key,label])=><label key={key}>{label}<input type="number" step="any" min="0" value={inputs[key as keyof Inventory]} onChange={e=>{setInputs({...inputs,[key]:Number(e.target.value)});clear();}}/></label>)}
 {tab==="scenario" && <><label>Demand multiplier<input type="number" step="0.1" min="0" max="5" value={demand} onChange={e=>{setDemand(Number(e.target.value));clear();}}/></label><label>Stock multiplier<input type="number" step="0.1" min="0" max="5" value={stock} onChange={e=>{setStock(Number(e.target.value));clear();}}/></label><label>Lead-time change (days)<input type="number" value={leadDelta} onChange={e=>{setLeadDelta(Number(e.target.value));clear();}}/></label><label>Procurement cost multiplier<input type="number" min="0" step="0.1" value={costFactor} onChange={e=>{setCostFactor(Number(e.target.value));clear();}}/></label><label>Holding cost multiplier<input type="number" min="0" step="0.1" value={holdingFactor} onChange={e=>{setHoldingFactor(Number(e.target.value));clear();}}/></label><label>Scenario budget<input type="number" min="0" value={budget} onChange={e=>{setBudget(Number(e.target.value));clear();}}/></label><label>Scenario service level<input type="number" min="0.5" max="0.999" step="0.01" value={serviceLevel} onChange={e=>{setServiceLevel(Number(e.target.value));clear();}}/></label></>}
 {tab!=="history" && <Button disabled={loading||(tab==="allocation"?runIds.length===0:tab==="simulation"?(!product||!store):!runId)} onClick={()=>void call()}>{loading?"Calculating...":"Run analysis"}</Button>}</section>
 {tab==="history" && (history.isFetching?<div className="panel loading">Loading review history...</div>:history.isError?<div className="error">{history.error.message}</div>:<Results data={{reviews:history.data??[]}}/>)}
 {review && !decision && <p>{review}</p>}
 {error&&<div className="error" role="alert">{error}</div>}{loading&&<div className="panel loading" role="status">Calculating simulated results...</div>}
 {decision?.projection && <section className="panel"><h2>Projected stock</h2><Chart option={{tooltip:{trigger:"axis"},legend:{},xAxis:{type:"category",data:decision.projection.map(p=>p.date)},yAxis:{type:"value",name:"Units"},series:[{type:"line",name:"Projected stock",data:decision.projection.map(p=>p.stock)},{type:"line",name:"Forecast demand",data:decision.projection.map(p=>p.demand)}]}}/></section>}
 {comparison && <section className="panel"><h2>Scenario comparison</h2><Chart option={{tooltip:{trigger:"axis"},legend:{},xAxis:{type:"category",data:["Recommended order","Projected shortage"]},yAxis:{type:"value",name:"Units"},series:[{type:"bar",name:"Baseline",data:[comparison.baseline.recommended_quantity,comparison.baseline.projected_shortage]},{type:"bar",name:"Scenario",data:[comparison.scenario.recommended_quantity,comparison.scenario.projected_shortage]}]}}/></section>}
 {tab==="simulation" && result && Array.isArray(result.policies) && <section className="panel"><h2>Simulated policy costs</h2><Chart option={{tooltip:{trigger:"axis"},xAxis:{type:"category",data:result.policies.map((p:{policy:string})=>p.policy)},yAxis:{type:"value",name:"Cost units"},series:[{type:"bar",name:"Relevant cost",data:result.policies.map((p:{total_relevant_cost:number})=>p.total_relevant_cost)}]}}/></section>}
 {result&&<><Results data={result}/><Downloads title={"Simulated inventory "+tab} data={result} filters={{inputs,runId,product,store,demand,stock}} assumptions="All inventory, supply and costs are simulated. Historical sales are a demand proxy."/></>}
 {decision&&<section className="panel"><h2>Simulated review</h2><div className="filters">{["review","approved","rejected"].map(status=><Button key={status} variant="outline" onClick={()=>void save(status)}>{status}</Button>)}</div><p>{review}</p></section>}</>;
}
