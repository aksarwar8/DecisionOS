export type QueryValue = string | number | boolean | null | undefined | number[];
export type Params = Record<string, QueryValue>;

export class ApiError extends Error {
  constructor(message: string, public status: number, public requestId: string | null) {
    super(message);
  }
}

export async function request<T>(path: string, options: {
  params?: Params; method?: "GET" | "POST"; body?: unknown; signal?: AbortSignal; timeout?: number;
} = {}): Promise<T> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(options.params ?? {})) {
    if (value === null || value === undefined || value === "") continue;
    for (const entry of Array.isArray(value) ? value : [value]) params.append(key, String(entry));
  }
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), options.timeout ?? 30000);
  const abort = () => controller.abort();
  options.signal?.addEventListener("abort", abort, { once: true });
  if (options.signal?.aborted) abort();
  try {
    const base = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
    const response = await fetch(`${base}${path}${params.size ? `?${params}` : ""}`, {
      method: options.method ?? "GET", signal: controller.signal,
      headers: options.body ? { "Content-Type": "application/json" } : undefined,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    const data: unknown = await response.json().catch((error: unknown) => { if (response.ok) throw error; return null; });
    if (!response.ok) {
      const detail = typeof data === "object" && data !== null && "detail" in data ? data.detail : null;
      const message = typeof detail === "string" ? detail : Array.isArray(detail)
        ? detail.map((item: { msg?: string }) => item.msg ?? "Invalid input").join(", ")
        : "The request could not be completed.";
      throw new ApiError(message, response.status, response.headers.get("X-Request-ID"));
    }
    return data as T;
  } catch (error) {
    if (controller.signal.aborted && !options.signal?.aborted) throw new ApiError("The request exceeded its time limit.", 0, null);
    throw error;
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", abort);
  }
}
