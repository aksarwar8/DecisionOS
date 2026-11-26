import React, { useState, lazy, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { BrowserRouter, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { Activity, BarChart3, Boxes, CalendarDays, ChevronRight, Database, LayoutDashboard, LineChart, Search, FileText, Settings, TrendingUp } from "lucide-react";
import { request } from "./api/client";
import { ThemeButton, useTheme } from "./components/ThemeButton";
import type { Config } from "./shared"; import "./styles.css";
const AnalyticsPage = lazy(() => import("./Analytics")); const Forecast = lazy(() => import("./Forecast")); const Models = lazy(() => import("./Models")); const Workspace = lazy(() => import("./Workspace"));
const configs: Record<string, Config> = {
  "/": { title: "Executive Overview", description: "Understand demand across the business.", path: "/analytics/sales-report", options: { view: "executive", aggregation: "weekly" } },
  "/sales": { title: "Sales Intelligence", description: "Explore historical demand and contribution.", path: "/analytics/sales-report", options: { view: "sales", aggregation: "weekly" } },
  "/products": { title: "Product Intelligence", description: "Compare product demand and identify trends.", path: "/analytics/product-rankings", options: { sort: "top", limit: "20" } },
  "/stores": { title: "Store & Category Intelligence", description: "Explore performance across stores and merchandise.", path: "/analytics/store-rankings", options: { sort: "top", limit: "10" } },
  "/seasonality": { title: "Seasonality & Events", description: "Explore historical demand and calendar associations.", path: "/analytics/seasonality", options: { group_by: "weekday" } },
  "/price": { title: "Price Intelligence", description: "Inspect weekly quoted prices and observed demand.", path: "/analytics/price-intelligence", product: true, store: true },
};
const navigation = [
  ["Overview", [["/", "Executive Overview", LayoutDashboard]]],
  ["Business intelligence", [["/sales", "Sales Intelligence", BarChart3], ["/products", "Product Intelligence", Boxes], ["/stores", "Store & Category", Database], ["/seasonality", "Seasonality & Events", CalendarDays], ["/price", "Price Intelligence", TrendingUp], ["/history", "Product–Store History", Search]]],
  ["Predictive intelligence", [["/forecast", "Demand Forecasting", LineChart], ["/models", "Model Intelligence", Activity]]],
  ["Workspace", [["/reports","Business Reports",FileText],["/system","System Status",Settings]]],
] as const;
function App() {
  const location = useLocation();
  const {dark,toggle} = useTheme();
  const [open, setOpen] = useState(false);
  const health = useQuery({ queryKey: ["health"], queryFn: ({ signal }) => request<{ status: string }>("/health", { signal }), retry: false, staleTime: 60000 });

  return <div className={dark ? "app dark" : "app"}><aside id="workspace-navigation" className={open ? "sidebar open" : "sidebar"}><div className="brand"><span className="brand-icon">D</span><div><strong>DecisionOS</strong><small>RETAIL INTELLIGENCE</small></div></div><nav>{navigation.map(([group, links]) => <div key={group}><div className="nav-label">{group}</div>{links.map(([url, label, Icon]) => <NavLink key={url} end={url === "/"} to={url} onClick={() => setOpen(false)}><Icon size={17}/>{label}</NavLink>)}</div>)}</nav><div className="sidebar-foot">Historical analytics workspace</div></aside><main><header><button className="menu" onClick={() => setOpen(!open)} aria-label="Toggle navigation" aria-expanded={open} aria-controls="workspace-navigation">☰</button><span className="breadcrumb">Workspace <ChevronRight size={14}/> {configs[location.pathname]?.title ?? navigation.flatMap(([, links]) => links.map(([url,label]) => ({url,label}))).find(item=>item.url===location.pathname)?.label}</span><div className="header-right"><span className="health"><i className={health.data?.status === "healthy" ? "online" : ""}/>{health.isPending ? "Checking API" : health.data?.status === "healthy" ? "API online" : "API unavailable"}</span><ThemeButton dark={dark} toggle={toggle}/></div></header><div className="content"><Suspense fallback={<div className="panel loading">Loading workspace...</div>}><Routes>{Object.entries(configs).map(([url, config]) => <Route key={url} path={url} element={<AnalyticsPage key={url} config={config} pathname={url}/>}/>) }<Route path="/forecast" element={<Forecast/>}/><Route path="/models" element={<Models/>}/><Route path="/history" element={<Workspace key="history" view="history"/>}/><Route path="/reports" element={<Workspace key="reports" view="reports"/>}/><Route path="/system" element={<Workspace key="system" view="system"/>}/></Routes></Suspense></div></main></div>;
}

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });
createRoot(document.getElementById("root")!).render(<React.StrictMode><QueryClientProvider client={queryClient}><BrowserRouter><App/></BrowserRouter></QueryClientProvider></React.StrictMode>);
