// @vitest-environment jsdom
import { ThemeButton, useTheme } from "./components/ThemeButton";
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import Analytics from "./Analytics";
import Forecast from "./Forecast";
import { reportContent } from "./reports";
import { request } from "./api/client";

vi.mock("./api/client",()=>({request:vi.fn(), ApiError:Error}));
vi.mock("./components/Chart",()=>({Chart:()=>null}));
const mocked=vi.mocked(request);
afterEach(()=>{cleanup(); mocked.mockReset();});
function mount(component:ReactNode) {
  const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});
  render(<QueryClientProvider client={client}>{component}</QueryClientProvider>);
}
function catalog(path:string) {
  if(path.endsWith("/products") && path.startsWith("/catalog")) return {products:[{product_id:4,item_id:"FOODS_1"}],total:1};
  if(path==="/catalog/stores") return [{store_id:1,store_code:"CA_1"}];
  return {};
}

test.each([["/products","Product",4,"product_ids"],["/stores","Store",1,"store_ids"]])("submits %s comparisons only after Load and clears stale results",async(path,label,id,key)=>{
  mocked.mockImplementation(async(path)=>path.endsWith("-comparison")?{observed_days:27}:catalog(path));
  mount(<Analytics pathname={path} config={{title:"Analytics",description:"Test",path:"/unused"}}/>);
  fireEvent.change(screen.getByLabelText("Analysis"),{target:{value:"comparison"}});
  await screen.findByRole("option",{name:label==="Product"?"FOODS_1":"CA_1"});
  fireEvent.change(screen.getByLabelText(label,{exact:true}),{target:{value:String(id)}});
  expect(mocked.mock.calls.some(([path])=>path.endsWith("-comparison"))).toBe(false);
  fireEvent.click(screen.getByRole("button",{name:"Load analysis"}));
  await screen.findByText("27");
  expect(mocked).toHaveBeenCalledWith(expect.stringMatching(/-comparison$/),expect.objectContaining({params:expect.objectContaining({[key]:[id]})}));
  fireEvent.change(screen.getByLabelText("Period"),{target:{value:"60"}});
  expect(screen.queryByText("27")).toBeNull();
});

test("forecast preview reports workload limits and keeps generation disabled",async()=>{
  mocked.mockImplementation(async(path)=>path.endsWith("scope-preview")?{candidate_pairs:100,estimated_rows:700,max_pairs:20,max_rows:500,within_limits:false}:catalog(path));
  mount(<Forecast/>);
  fireEvent.change(screen.getByLabelText("Scope"),{target:{value:"store"}});
  await screen.findByRole("option",{name:"CA_1"});
  fireEvent.change(screen.getByLabelText("Store",{exact:true}),{target:{value:"1"}});
  fireEvent.click(screen.getByRole("button",{name:"Preview workload"}));
  await screen.findByText(/Workload exceeds/);
  expect((screen.getByRole("button",{name:"Generate batch forecast"}) as HTMLButtonElement).disabled).toBe(true);
  expect(mocked).toHaveBeenCalledWith("/forecast/scope-preview",expect.objectContaining({method:"POST",body:expect.objectContaining({scope:"store",store_ids:[1],horizon:7})}));
  fireEvent.change(screen.getByLabelText("Horizon"),{target:{value:"14"}});
  await waitFor(()=>expect(screen.queryByText(/Workload exceeds/)).toBeNull());
});

test("exports fixed metadata and actual values without losing numeric zero",()=>{
  const result={period_start:"2016-01-01",stats:[{demand:0},{demand:null},{label:"=example"}]};
  const time=new Date("2026-01-01T00:00:00Z");
  const csv=reportContent("Sales",result,{store:"CA_1"},"units",time,false);
  expect(csv).toContain('"stats.0.demand","0"');
  expect(csv).toContain('"stats.1.demand",""');
  expect(csv).toContain("'=example");
  const md=reportContent("Sales",result,{store:"CA_1"},"units",time,true);
  expect(md).toContain("2026-01-01T00:00:00.000Z");
  expect(md).toContain("2016-01-01");
  expect(md).toContain("CA_1");
});

test("shows loading and a meaningful empty state",async()=>{
  let resolve: (value: unknown) => void = () => {};
  mocked.mockImplementation(async(path)=>path==="/analytics/sales-report"?new Promise(done=>{resolve=done;}):catalog(path));
  mount(<Analytics pathname="/sales" config={{title:"Sales",description:"Historical demand",path:"/analytics/sales-report"}}/>);
  fireEvent.click(screen.getByRole("button",{name:"Load analysis"}));
  await screen.findByRole("status");
  resolve({trend:[]});
  await screen.findByText("No records match this scope.");
  expect(screen.queryByRole("status")).toBeNull();
});

test("persists the theme preference across a fresh mount",()=>{
  function Example() {
    const theme=useTheme();
    return <ThemeButton {...theme}/>;
  }
  localStorage.removeItem("decisionos-theme");
  const first=render(<Example/>);
  const control=screen.getByRole("button",{name:"Toggle color theme"});
  expect(control.getAttribute("aria-pressed")).toBe("false");
  fireEvent.click(control);
  expect(control.getAttribute("aria-pressed")).toBe("true");
  first.unmount();
  render(<Example/>);
  expect(screen.getByRole("button",{name:"Toggle color theme"}).getAttribute("aria-pressed")).toBe("true");
  localStorage.removeItem("decisionos-theme");
});
