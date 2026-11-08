// Typed client for the Titan brain (agent/server.py). Doors call only this HTTP API.
// Shapes come from contract-types.ts (copied from contracts/generated/types.ts; never edit by hand).
import type * as C from "./contract-types";

export type * as Contract from "./contract-types";

export const BRAIN_URL: string = process.env.NEXT_PUBLIC_BRAIN_URL ?? "http://localhost:8000";
export const MAYA = "usr_maya";

export type ProtectionName = "sim_protection" | "port_out_protection" | "scam_block";
export type DemoScenario = "t1" | "t2" | "t3" | "t5";

/** Brain 4xx bodies are FastAPI-wrapped: { detail: { error, detail? } }. */
export type BrainErrorBody = { detail?: { error?: string; detail?: string[] } | string } | null;

export class BrainError extends Error {
  status: number;
  body: BrainErrorBody;
  constructor(status: number, body: BrainErrorBody, path: string) {
    super(`Brain ${status} on ${path}`);
    this.name = "BrainError";
    this.status = status;
    this.body = body;
  }
  /** e.g. "pause_required" (409 on a protection change) or "unsafe_now" (409 on an approval). */
  get code(): string | undefined {
    const d = this.body?.detail;
    return typeof d === "object" && d ? d.error : undefined;
  }
}

async function call<T>(path: string, init?: { method?: "GET" | "POST"; body?: unknown }): Promise<T> {
  const res = await fetch(`${BRAIN_URL}${path}`, {
    method: init?.method ?? "GET",
    headers: init?.body === undefined ? undefined : { "content-type": "application/json" },
    body: init?.body === undefined ? undefined : JSON.stringify(init.body),
    cache: "no-store",
  });
  if (!res.ok) {
    let body: BrainErrorBody = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    throw new BrainError(res.status, body, path);
  }
  return (await res.json()) as T;
}

export const getProtections = (uid: string = MAYA) =>
  call<C.ProtectionState>(`/protections/${uid}`);

export const check = (req: C.CheckRequest) =>
  call<C.CheckResponse>("/check", { method: "POST", body: req });

export const setProtection = (name: ProtectionName, body: C.ProtectionChangeRequest, uid: string = MAYA) =>
  call<C.ProtectionState>(`/protections/${uid}/${name}`, { method: "POST", body });

export const requestTransferPin = (uid: string = MAYA) =>
  call<{ check: C.CheckResponse; protections: C.ProtectionState }>(`/transfer-pin/${uid}`, { method: "POST" });

export type EventAck = { accepted: boolean; duplicate: boolean; case_id: string | null; trigger: string | null };
export const postEvent = (ev: C.Event) => call<EventAck>("/events", { method: "POST", body: ev });

export const getTimeline = (uid: string = MAYA) => call<C.Timeline>(`/users/${uid}/timeline`);

export const getCases = (uid?: string) =>
  call<C.Case[]>(uid ? `/cases?user_id=${encodeURIComponent(uid)}` : "/cases");

export const getCase = (id: string) => call<C.CaseDetail>(`/cases/${encodeURIComponent(id)}`);

export const demoPlay = (s: DemoScenario) =>
  call<{ ok: boolean; scenario: string; user_id: string }>(`/demo/play/${s}`, { method: "POST" });

export const demoReset = () => call<{ ok: boolean }>("/demo/reset", { method: "POST" });

export const newEventId = () => `evt_${crypto.randomUUID().replace(/-/g, "").slice(0, 16)}`;
export const nowIso = () => new Date().toISOString().replace(/\.\d{3}Z$/, "Z");

/**
 * Live StepEvents for one case over SSE. The brain replays history on every connection and closes
 * the stream after `type: "done"`, so this dedupes by seq and closes the EventSource on done
 * (otherwise the browser reconnects and every step arrives twice). Returns an unsubscribe.
 */
export function subscribeCase(
  id: string,
  onStep: (s: C.StepEvent) => void,
  onCase: (c: C.Case) => void,
  onError?: () => void,
): () => void {
  const es = new EventSource(`${BRAIN_URL}/cases/${encodeURIComponent(id)}/stream`);
  const seen = new Set<number>();
  es.addEventListener("step", (e) => {
    const step = JSON.parse((e as MessageEvent<string>).data) as C.StepEvent;
    if (seen.has(step.seq)) return;
    seen.add(step.seq);
    onStep(step);
    if (step.type === "done") es.close();
  });
  es.addEventListener("case", (e) => onCase(JSON.parse((e as MessageEvent<string>).data) as C.Case));
  es.onerror = () => {
    // CLOSED means the browser gave up (e.g. 404 after a brain restart wiped the store).
    if (es.readyState === EventSource.CLOSED) onError?.();
  };
  return () => es.close();
}
