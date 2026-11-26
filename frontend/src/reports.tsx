import { Button } from "./components/ui/button";
import type { Row } from "./shared";

export function reportContent(title: string, data: Row, filters: object, assumptions: string, now: Date, markdown: boolean) {
  const metadata = {title, generated_at: now.toISOString(), filters, assumptions};
  if (markdown) return "# " + title + "\n\nGenerated " + metadata.generated_at + "\n\n" + assumptions + "\n\n## Filters\n\n```json\n" + JSON.stringify(filters, null, 2) + "\n```\n\n## Results\n\n```json\n" + JSON.stringify(data, null, 2) + "\n```\n";
  const rows: [string, unknown][] = Object.entries(metadata);
  function flatten(value: unknown, path: string) {
    if (value && typeof value === "object" && Object.keys(value).length) {
      Object.entries(value).forEach(([key, child]) => flatten(child, path + "." + key));
    } else rows.push([path, value]);
  }
  Object.entries(data).forEach(([key, value]) => flatten(value, key));
  const quote = (value: unknown) => {
    const raw = value == null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value);
    const safe = typeof value === "string" && /^[\s]*[=+@-]/.test(raw) ? "'" + raw : raw;
    return '"' + safe.replaceAll('"', '""') + '"';
  };
  return ["field,value", ...rows.map(row => row.map(quote).join(","))].join("\r\n");
}

export function Downloads({title,data,filters,assumptions}: {title:string;data:Row;filters:object;assumptions:string}) {
  function download(markdown: boolean) {
    const content = reportContent(title,data,filters,assumptions,new Date(),markdown);
    const url = URL.createObjectURL(new Blob([content], {type: markdown ? "text/markdown;charset=utf-8" : "text/csv;charset=utf-8"}));
    const link = document.createElement("a");
    link.href = url;
    link.download = title.toLowerCase().replace(/[^a-z0-9]+/g,"-") + (markdown ? ".md" : ".csv");
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <div className="pagination"><Button variant="outline" onClick={() => download(false)}>Download CSV</Button><Button variant="outline" onClick={() => download(true)}>Download Markdown</Button></div>;
}
