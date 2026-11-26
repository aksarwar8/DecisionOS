import type { EChartsOption, SeriesOption } from "echarts";
import { Chart } from "./Chart";
import type { Row } from "../shared";

export function AnalysisCharts({data,path,metric}: {data:Row;path:string;metric:string}) {
  const list = (key:string) => Array.isArray(data[key]) ? data[key] as Row[] : [];
  const charts: {title:string;option:EChartsOption}[] = [];
  const axis = {tooltip:{trigger:"axis" as const},legend:{},grid:{left:65,right:65,top:50,bottom:55}};
  const lines = (rows:Row[], group:(r:Row)=>string, date:string, value:string, title:string) => {
    if (!rows.length) return;
    const dates = [...new Set(rows.map(r=>String(r[date])))].sort();
    const groups = [...new Set(rows.map(group))];
    charts.push({title,option:{...axis,xAxis:{type:"category",data:dates},yAxis:{type:"value",name:"Units"},series:groups.map(name=>{
      const values = new Map(rows.filter(r=>group(r)===name).map(r=>[String(r[date]),r[value] as number | null]));
      return {type:"line",name, data:dates.map(d=>values.get(d)??null),connectNulls:false};
    })}});
  };
  const bars = (rows:Row[],label:string,value:string,title:string) => {
    if (rows.length) charts.push({title,option:{...axis,xAxis:{type:"category",data:rows.map(r=>String(r[label])),axisLabel:{rotate:25}},yAxis:{type:"value"},series:[{type:"bar",name:title,data:rows.map(r=>r[value] as number|null)}]}});
  };
  if (data.breakdowns && typeof data.breakdowns === "object") {
    const breakdowns = data.breakdowns as Record<string,Row[]>;
    if (breakdowns.category?.length) charts.push({title:"Category contribution",option:{tooltip:{trigger:"item"},legend:{bottom:0},series:[{type:"pie",radius:["35%","68%"],data:breakdowns.category.map(r=>({name:String(r.label),value:r.total_demand as number}))}]}});
    bars(breakdowns.state??[],"label","total_demand","Demand by state");
  }
  bars(list("top_products"),"code","total_demand","Top products by units");
  bars(list("top_stores"),"code","total_demand","Top stores by units");
  if (data.comparison && typeof data.comparison==="object" && "standardized_baseline_average" in data.comparison) {
    const comparison = data.comparison as Row;
    bars([{label:"Event days",average:comparison.matched_average_demand},{label:"Matched weekdays",average:comparison.standardized_baseline_average}],"label","average","Demand per matched observed day");
  }
  const products = list("products"); const trend = list("trend");
  if (trend.some(r=>"product_id" in r)) lines(trend,r=>String(products.find(p=>p.product_id===r.product_id)?.item_id ?? r.product_id),"period","total_demand","Product demand");
  else if (trend.some(r=>"group_id" in r)) lines(trend,r=>String(r.label),"period","total_demand","Demand by group");
  else if (trend.some(r=>"status" in r)) lines(trend,r=>String(r.status),"period","average_demand_per_observed_store_day","SNAP and non-SNAP demand per observed store-day");
  else lines(trend,()=>"Demand","period","total_demand","Historical demand");
  bars(list("buckets"),"label","average_daily_demand","Demand per observed day");
  bars(list("offsets"),"offset","average_daily_demand","Observed daily demand around the event");
  bars(list("summary"),path.endsWith("abc-analysis")?"classification":"segment","total_demand","Demand contribution by group");
  if (products.some(r=>"cumulative_pct" in r)) charts.push({title:"Volume-based ABC Pareto",option:{...axis,xAxis:{type:"category",name:"Rank",data:products.map(r=>String(r.rank))},yAxis:[{type:"value",name:"Units"},{type:"value",name:"Cumulative %",min:0,max:100}],series:[{name:"Units",type:"bar",data:products.map(r=>r.total_demand as number)},{name:"Cumulative contribution",type:"line",yAxisIndex:1,data:products.map(r=>r.cumulative_pct as number|null),markLine:{data:[{yAxis:80},{yAxis:95}]}}]}});
  const cells = list("cells");
  if (cells.length) {
    const x = [...new Set(cells.map(r=>String(r.merchandise_label)))]; const y = [...new Set(cells.map(r=>String(r.geography_label)))];
    const values = cells.flatMap(r=>typeof r[metric]==="number" ? [[x.indexOf(String(r.merchandise_label)),y.indexOf(String(r.geography_label)),r[metric]]] : []);
    const magnitudes = values.map(row=>row[2]);
    charts.push({title:"Demand matrix",option:{tooltip:{formatter:p=>{const point = Array.isArray(p)?p[0]:p; const [column,row,value]=point.data as number[]; return [y[row],x[column],String(value)].join(" · ").replaceAll("&","&amp;").replaceAll("<","&lt;");}},grid:{left:80,bottom:80},xAxis:{type:"category",data:x,axisLabel:{rotate:25}},yAxis:{type:"category",data:y},visualMap:{min:Math.min(0,...magnitudes),max:Math.max(1,...magnitudes),orient:"horizontal",left:"center",bottom:0,inRange:{color:["#e0e7ff","#315bcc","#192d66"]}},series:[{type:"heatmap",data:values}]}});
  }
  const composition = list("composition");
  if (composition.length) {
    const groups = [...new Set(composition.map(r=>String(r.group_label)))];
    const series: SeriesOption[] = [...new Set(composition.map(r=>String(r.category_label)))].map(name=>({type:"bar",stack:"demand",name,data:groups.map(group=>composition.find(r=>r.group_label===group && r.category_label===name)?.total_demand as number ?? null)}));
    charts.push({title:"Category composition",option:{...axis,xAxis:{type:"category",data:groups},yAxis:{type:"value",name:"Units"},series}});
  }
  const weekly = list("weekly");
  if (weekly.length) {
    charts.push({title:"Observed price and demand",option:{...axis,xAxis:{type:"category",data:weekly.map(r=>String(r.week_start))},yAxis:[{type:"value",name:"Units"},{type:"value",name:"Unit price"}],series:[{name:"Demand",type:"bar",data:weekly.map(r=>r.total_demand as number|null)},{name:"Unit price",type:"line",yAxisIndex:1,data:weekly.map(r=>r.unit_price as number|null),connectNulls:false}]}});
    charts.push({title:"Weekly price–demand association",option:{tooltip:{trigger:"item"},xAxis:{name:"Unit price",type:"value"},yAxis:{name:"Units",type:"value"},series:[{type:"scatter",data:weekly.filter(r=>r.unit_price!=null && r.total_demand!=null).map(r=>[r.unit_price as number,r.total_demand as number])}]}});
  }
  return <>{charts.map(({title,option})=><section className="panel" key={title}><h2>{title}</h2><Chart option={option}/></section>)}</>;
}
