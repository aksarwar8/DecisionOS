import { useEffect, useRef } from "react";
import { init, use, type EChartsType } from "echarts/core";
import { BarChart, HeatmapChart, LineChart, PieChart, ScatterChart } from "echarts/charts";
import { GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, VisualMapComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsOption } from "echarts";

use([BarChart, HeatmapChart, LineChart, PieChart, ScatterChart, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent, VisualMapComponent, CanvasRenderer]);

export function Chart({option}: {option:EChartsOption}) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<EChartsType | null>(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const instance = init(node);
    chart.current = instance;
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(node);
    return () => { observer.disconnect(); instance.dispose(); chart.current = null; };
  }, []);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const root = node.closest(".app");
    const update = () => {
      const dark = root?.classList.contains("dark");
      const color = dark ? "#cbd5e1" : "#475569";
      const axisStyle = {axisLabel:{color},nameTextStyle:{color}};
      chart.current?.setOption({...option,textStyle:{color},xAxis:option.xAxis && (Array.isArray(option.xAxis)?option.xAxis.map(axis=>({...axisStyle,...axis})):{...axisStyle,...option.xAxis}),yAxis:option.yAxis && (Array.isArray(option.yAxis)?option.yAxis.map(axis=>({...axisStyle,...axis})):{...axisStyle,...option.yAxis})}, true);
    };
    update();
    const observer = new MutationObserver(update);
    if (root) observer.observe(root,{attributes:true,attributeFilter:["class"]});
    return () => observer.disconnect();
  },[option]);
  return <div ref={ref} className="chart" role="img" aria-label="Analytics chart"/>;
}
