import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query"; import { Search } from "lucide-react"; import { request } from "./api/client"; import { Button } from "./components/ui/button"; import { Chart } from "./components/Chart";
export type Row = Record<string, unknown>;
type Product = { product_id: number; item_id: string };
type Store = { store_id: number; store_code: string };
type Catalog = { products: Product[]; total: number };
export type Config = { title: string; description: string; path: string; options?: Record<string, string>; product?: boolean; store?: boolean };
export const titleize = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
const format = (value: unknown): string => value === null || value === undefined ? "—" : typeof value === "number" ? new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value) : typeof value === "object" ? JSON.stringify(value) : String(value);

export function CatalogSelect({ product, value, onChange, category, department, state, onPick }: { product?: boolean; value: string; onChange: (value: string) => void; category?: string; department?: string; state?: string; onPick?: (id: number, label: string) => void }) {
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState(""); const [offset, setOffset] = useState(0); const [selected, setSelected] = useState<{id: string; label: string} | null>(null);
  useEffect(() => { const timer = setTimeout(() => { setDebounced(search); setOffset(0); }, 300); return () => clearTimeout(timer); }, [search]);
  const query = useQuery<Catalog | Store[]>({ queryKey: ["catalog", product, debounced, category, department, state, offset], queryFn: ({ signal }) => product
    ? request<Catalog>("/catalog/products", { params: { search: debounced, category, department, limit: 50, offset }, signal })
    : request<Store[]>("/catalog/stores", { params: { state }, signal }), staleTime: 120000, retry: false });
  const entries = product ? (query.data as Catalog | undefined)?.products.map((p) => [p.product_id, p.item_id] as const) : (query.data as Store[] | undefined)?.map((s) => [s.store_id, s.store_code] as const);
  return <div className="catalog-control"><span>{product ? "Product" : "Store"}</span>{product && <span className="searchbox"><Search size={14}/><input aria-label="Search product codes" placeholder="Search item code" value={search} onChange={(e) => setSearch(e.target.value)}/></span>}<select aria-label={product ? "Product" : "Store"} value={value} onChange={(e) => { const id = e.target.value; const label = e.target.selectedOptions[0]?.text ?? id; setSelected({id,label}); onChange(id); if (id) onPick?.(Number(id),label); }}><option value="">Select {product ? "product" : "store"}</option>{value && selected?.id === value && !entries?.some(([id]) => String(id) === value) && <option value={value}>{selected.label}</option>}{entries?.map(([id, code]) => <option value={id} key={id}>{code}</option>)}</select>{product && <span className="pagination"><Button variant="outline" disabled={!offset} onClick={() => setOffset(Math.max(0,offset-50))}>Previous items</Button><Button variant="outline" disabled={offset + 50 >= ((query.data as Catalog | undefined)?.total ?? 0)} onClick={() => setOffset(offset+50)}>More items</Button></span>}{query.isError && <small>Catalog unavailable</small>}</div>;
}

export function Results({ data }: { data: Row }) {
  const scalars = Object.entries(data).filter(([, value]) => value === null || ["string", "number", "boolean"].includes(typeof value));
  const display = (key:string,value:unknown) => typeof value === "number" && (key.endsWith("_pct") || key.startsWith("percentage_")) ? format(value)+"%" : format(value);
  const arrays = Object.entries(data).filter(([, value]) => Array.isArray(value) && (!value.length || typeof value[0] === "object")) as [string, Row[]][];
  return <><div className="metrics">{scalars.map(([key, value]) => <div className="metric" key={key}><span>{titleize(key)}</span><strong className={typeof value==="number" && /change|growth/.test(key) ? (value>0?"positive":value<0?"negative":"") : ""}>{display(key,value)}</strong></div>)}</div>{Object.entries(data).filter(([, value]) => value && typeof value === "object" && !Array.isArray(value)).map(([key, value]) => <section className="panel" key={key}><h2>{titleize(key)}</h2><Results data={value as Row}/></section>)}{arrays.map(([key, rows]) => <section className="panel" key={key}><div className="panel-heading"><div><h2>{titleize(key)}</h2><p>{rows.length} records in this result</p></div></div>{rows.length ? <DataView rows={rows}/> : <p className="empty">No records match this scope.</p>}</section>)}</>;
}
function DataView({ rows }: { rows: Row[] }) {
  const [page, setPage] = useState(0);
  const keys = Array.from(new Set(rows.flatMap(Object.keys)));
  const dateKey = keys.find((key) => ["date"].includes(key));
  const valueKey = keys.find((key) => ["prediction", "sales_quantity"].includes(key));
  return <>{dateKey && valueKey && <Chart option={{ tooltip: { trigger: "axis" }, grid: { left: 55, right: 20, top: 25, bottom: 40 }, xAxis: { type: "category", data: rows.map((r) => format(r[dateKey])) }, yAxis: { type: "value" }, series: [{ type: "line", data: rows.map((r) => r[valueKey] ?? null), smooth: false, color: "#5574d9" }] }}/>}<div className="table-scroll"><table><thead><tr>{keys.map((key) => <th key={key}>{titleize(key)}</th>)}</tr></thead><tbody>{rows.slice(page * 15, (page + 1) * 15).map((row, index) => <tr key={index}>{keys.map((key) => <td key={key}>{format(row[key])}</td>)}</tr>)}</tbody></table></div>{rows.length > 15 && <div className="pagination"><Button variant="outline" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button><span>Page {page + 1} of {Math.ceil(rows.length / 15)}</span><Button variant="outline" disabled={(page + 1) * 15 >= rows.length} onClick={() => setPage(page + 1)}>Next</Button></div>}</>;
}


export function CatalogFilter({kind,value,onChange,category}: {kind:"category"|"department"|"state";value:string;onChange:(value:string)=>void;category?:string}) {
  const key = {category:"categories",department:"departments",state:"states"}[kind];
  const query = useQuery({queryKey:["catalog",key,category],queryFn:({signal})=>request<Record<string,string[]>>("/catalog/"+key,{params:{category},signal}),staleTime:120000});
  return <label>{titleize(kind)}<select value={value} onChange={e=>onChange(e.target.value)}><option value="">All {key}</option>{query.data?.[key]?.map(label=><option key={label}>{label}</option>)}</select>{query.isError && <small>Catalog unavailable</small>}</label>;
}

export function MultiSelect({product,values,onChange,max=5,category,department,state}: {product?:boolean;values:number[];onChange:(ids:number[])=>void;max?:number;category?:string;department?:string;state?:string}) {
  const [labels,setLabels]=useState<Record<number,string>>({});
  return <div><CatalogSelect product={product} category={category} department={department} state={state} value="" onChange={()=>{}} onPick={(id,label)=>{if(values.length < max && !values.includes(id)){setLabels({...labels,[id]:label});onChange([...values,id]);}}}/>
    <div className="selection-chips">{values.map(id=><Button key={id} variant="outline" onClick={()=>onChange(values.filter(entry=>entry!==id))} aria-label={"Remove "+labels[id]}>{labels[id]} ×</Button>)}</div><small>{values.length} of {max} selected</small></div>;
}
