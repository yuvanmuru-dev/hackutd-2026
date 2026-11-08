// Pure view model for the guardian screen. No fetch, no clock.
// Driven only by StepEvent title/type/agent/stage (D-028): `data` differs between MOCK and the real workflow.
import type { Contract as C } from "@/lib/api/client";

export type PipelineAgent = "context" | "risk" | "verifier" | "response";

export const PIPELINE: { agent: PipelineAgent; label: string; job: string }[] = [
  { agent: "context", label: "Context", job: "Gathers the facts" },
  { agent: "risk", label: "Risk", job: "Scores the threat" },
  { agent: "verifier", label: "Verifier", job: "Checks every claim" },
  { agent: "response", label: "Response", job: "Acts and reaches her" },
];

/** D-028 + D-036: re-fetch GET /cases/{id} once on these step types. No polling. */
export const REFETCH_TYPES: ReadonlySet<C.StepEvent["type"]> = new Set<C.StepEvent["type"]>([
  "action",
  "approval_needed",
  "approved",
  "summary",
  "done",
  "score",
  "verify",
]);

export interface GuardianView {
  steps: C.StepEvent[];
  columns: Record<PipelineAgent, C.StepEvent[]>;
  activeAgent: PipelineAgent | null;
  systemLine: C.StepEvent | null;
  feed: C.StepEvent[];
  approvals: C.StepEvent[];
  verdictRevealed: boolean;
  verified: boolean;
  awaiting: boolean;
  needsApproval: boolean;
  errors: C.StepEvent[];
  done: boolean;
  /** The brain's own "Run failed" error, if the run ended on one. */
  failed: C.StepEvent | null;
  callMarkers: C.Event[];
}

const isPipeline = (a: C.StepEvent["agent"]): a is PipelineAgent =>
  a === "context" || a === "risk" || a === "verifier" || a === "response";

export const isDeclined = (s: C.StepEvent) => s.type === "action" && s.title.startsWith("Declined");

export function deriveView(detail: C.CaseDetail | null, input: C.StepEvent[]): GuardianView {
  const seen = new Set<number>();
  const steps = [...input]
    .sort((a, b) => a.seq - b.seq)
    .filter((s) => (seen.has(s.seq) ? false : (seen.add(s.seq), true)));

  const columns: Record<PipelineAgent, C.StepEvent[]> = { context: [], risk: [], verifier: [], response: [] };
  const feed: C.StepEvent[] = [];
  const approvals: C.StepEvent[] = [];
  const errors: C.StepEvent[] = [];
  let activeAgent: PipelineAgent | null = null;
  let systemLine: C.StepEvent | null = null;
  let verdictRevealed = false;
  let verified = false;
  let needsApproval = false;
  let done = false;

  for (const s of steps) {
    if (isPipeline(s.agent)) {
      columns[s.agent].push(s);
      activeAgent = s.agent;
    }
    if (s.agent === "system") systemLine = s;
    if (s.type === "message" || s.type === "transcript") feed.push(s);
    if (s.type === "approval_needed" || s.type === "approved" || isDeclined(s)) approvals.push(s);
    if (s.type === "approval_needed") needsApproval = true;
    if (s.type === "approved" || s.type === "done") needsApproval = false;
    if (s.type === "error") errors.push(s);
    if (s.type === "score") verdictRevealed = true;
    if (s.type === "verify") verified = true;
    if (s.type === "done") done = true;
  }

  const last = steps.at(-1);
  const awaiting = !done && last?.agent === "system" && last.stage === "await";
  const callId = detail?.call?.call_id;
  const callMarkers = callId ? (detail?.timeline ?? []).filter((e) => e.call_id === callId) : [];

  return {
    steps,
    columns,
    activeAgent: done ? null : activeAgent,
    systemLine,
    feed,
    approvals,
    verdictRevealed,
    verified,
    awaiting,
    needsApproval,
    errors,
    done,
    failed: errors.find((e) => e.agent === "system") ?? null,
    callMarkers,
  };
}

export const shouldRefetch = (s: C.StepEvent) => REFETCH_TYPES.has(s.type);

const THREAT_WORDS: Record<C.RiskScore["threat"], string> = {
  takeover: "Account takeover",
  coached: "Coached victim",
  scam_text: "Scam text",
  bot: "Bot",
  legit: "Looks legitimate",
};

export const wordsFor = (t: C.RiskScore["threat"] | null | undefined) => (t ? THREAT_WORDS[t] : "Still checking");

const CONF_WORDS = { low: "Low confidence", medium: "Medium confidence", high: "High confidence" } as const;

export function confidenceWords(
  risk: C.RiskScore | null | undefined,
  head?: { confidence: C.Case["confidence"] } | null,
): string {
  const level = risk?.confidence ?? head?.confidence ?? null;
  if (!level) return "Confidence not set yet";
  if (!risk) return CONF_WORDS[level];
  const pct = Math.round(risk.probability * 100);
  return `${CONF_WORDS[level]} · ${pct}%${risk.calibrated ? "" : " (uncalibrated)"}`;
}

const PRODUCT_NAMES: Record<string, string> = {
  port_out_protection: "Port Out Protection",
  sim_protection: "SIM Protection",
  scam_block: "Scam Block",
};

/** T-Mobile's product names are proper nouns: fix their case in any text we display (brain text included). */
export function productCase(text: string): string {
  return text
    .replace(/\bport[ -]out protection\b/gi, "Port Out Protection")
    .replace(/\bsim protection\b/gi, "SIM Protection")
    .replace(/\bscam block\b/gi, "Scam Block")
    .replace(/\btransfer pin(s?)\b/gi, "Transfer PIN$1")
    .replace(/\baccount takeover protection\b/gi, "Account Takeover Protection");
}

/** Readable labels for timeline events on the call bar. */
export function markerLabel(e: C.Event): string {
  const d = e.data as Record<string, unknown>;
  switch (e.type) {
    case "call.started":
      return "Call started";
    case "call.ended":
      return "Call ended";
    case "login":
      return d.new_device ? "Signed in on a new device" : "Signed in";
    case "portal.signals":
      return "Portal behavior";
    case "protection.changed":
      return `${PRODUCT_NAMES[String(d.name)] ?? productCase(String(d.name ?? "protection").replace(/_/g, " "))} ${d.enabled ? "on" : "off"}`;
    case "transfer_pin.requested":
      return "Transfer PIN requested";
    case "sim_swap.requested":
      return "SIM swap requested";
    case "otp.sent":
      return "Code sent";
    default:
      return e.type.replace(/[._]/g, " ");
  }
}

/** Markers that mean "she was talked into this": shown in the accent on the call bar. */
export const isRiskyMarker = (e: C.Event) => {
  const d = e.data as Record<string, unknown>;
  return (
    (e.type === "protection.changed" && d.enabled === false) ||
    e.type === "transfer_pin.requested" ||
    e.type === "sim_swap.requested" ||
    e.type === "otp.sent"
  );
};

export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}
