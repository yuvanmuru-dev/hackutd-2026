// The guardian screen's story: one question ("what's happening to Maya, and what did Titan do?") answered
// from the same CaseDetail + steps the brain streams. Pure functions, no fetch; the clock is passed in.
//
// ONE CLOCK: every time on the screen is "time since the call started" (or since the case opened when
// there is no call), formatted m:ss by formatDuration. Nothing else on the screen shows a time of day.
import type { Contract as C } from "@/lib/api/client";
import { formatDuration, isRiskyMarker, markerLabel, type GuardianView } from "./derive";

export type Stage = 1 | 2 | 3 | 4;

export interface StoryStep {
  n: Stage;
  title: string;
  line: string;
  state: "done" | "now" | "next";
}

export type ThreadItem =
  | { kind: "bubble"; id: string; from: "titan" | "maya"; text: string }
  | { kind: "call"; id: string; text: string };

export interface Story {
  stage: Stage;
  headline: string;
  steps: StoryStep[];
  thread: ThreadItem[];
  /** "Delivered" goes under this bubble (Maya's last sent message), when there is one. */
  deliveredId: string | null;
  typing: boolean;
  chip: string;
  chipTone: "live" | "safe" | "neutral";
  /** Seconds on the one clock at `now`. */
  clock: number;
}

const ms = (iso: string) => Date.parse(iso);

/** Base of the one clock: the call's start, else when the case opened. */
export function clockBase(detail: C.CaseDetail | null): number | null {
  if (!detail) return null;
  return ms(detail.call?.started_at ?? detail.created_at);
}

const at = (base: number | null, iso: string | undefined) =>
  base === null || !iso ? "" : formatDuration((ms(iso) - base) / 1000);

const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);

const SHORT: Partial<Record<C.Action["kind"], string>> = {
  relock: "Protection back on",
  hold_transfer_pin: "PIN held 24 h",
  require_step_up: "Extra checks on",
  reset_pin: "Account PIN reset",
  revoke_transfer_pin: "Transfer PIN cancelled",
  sign_out_sessions: "Other devices signed out",
  report_number: "Number reported",
};
const short = (a: C.Action) => SHORT[a.kind] ?? a.description;

/** Split a long text into at most 4 short bubbles at sentence ends (iMessage-sized, ~110 chars). */
export function splitBubbles(text: string): string[] {
  const clean = text.replace(/^Titan\s*[:·]\s*/, "").replace(/^Case\s+[A-Z]+-\d+\.\s*/, "").trim();
  const sentences = clean.match(/[^.!?]+[.!?]+["”’)]*\s*|[^.!?]+$/g)?.map((s) => s.trim()).filter(Boolean) ?? [clean];
  const out: string[] = [];
  for (const s of sentences) {
    const last = out.at(-1);
    if (last !== undefined && (last.length + s.length < 110 || out.length === 4)) out[out.length - 1] = `${last} ${s}`;
    else out.push(s);
  }
  return out;
}

function threadOf(messages: C.Message[]): { items: ThreadItem[]; deliveredId: string | null } {
  const sorted = [...messages].sort((a, b) => a.ts.localeCompare(b.ts));
  const items: ThreadItem[] = [];
  let deliveredId: string | null = null;
  for (let i = 0; i < sorted.length; i++) {
    const m = sorted[i];
    if (m.channel === "voice") {
      // Titan's phone call is one centered system row, however many transcript lines it had.
      let j = i;
      while (j + 1 < sorted.length && sorted[j + 1].channel === "voice") j++;
      const secs = Math.max(1, (ms(sorted[j].ts) - ms(m.ts)) / 1000 + 8);
      items.push({ kind: "call", id: m.message_id, text: `Titan called Maya · ${formatDuration(secs)}` });
      i = j;
      continue;
    }
    const from = m.direction === "out" ? "titan" : "maya";
    splitBubbles(m.text).forEach((text, k) => items.push({ kind: "bubble", id: `${m.message_id}-${k}`, from, text }));
    if (from === "maya") deliveredId = `${m.message_id}-${splitBubbles(m.text).length - 1}`;
  }
  return { items, deliveredId };
}

export function storyOf(detail: C.CaseDetail | null, head: C.Case | null, view: GuardianView, now: number): Story {
  const status = head?.status ?? detail?.status ?? "open";
  const call = detail?.call ?? null;
  const base = clockBase(detail);
  const risky = view.callMarkers.filter(isRiskyMarker);
  const actions = detail?.actions ?? [];
  const done = actions.filter((a) => a.status === "applied" || a.status === "approved");
  const mayaApproved = actions.filter((a) => a.requires_approval && (a.status === "applied" || a.status === "approved"));
  const responding = view.columns.response.length > 0;

  const stage: Stage =
    status === "watching" || status === "closed"
      ? 4
      : done.length > 0 || responding
        ? 3
        : risky.length > 0 || view.verdictRevealed
          ? 2
          : 1;

  const claimsCarrier = /t-?mobile/i.test(call?.caller_name ?? "");
  const firstRisk = risky[0];
  const topReason = detail?.risk?.top_reasons.find((r) => r.contribution > 0)?.text ?? null;

  const headline = {
    1: call
      ? claimsCarrier
        ? "A caller claiming to be T-Mobile is on the line with Maya."
        : "An unverified caller is on the line with Maya."
      : `${head?.title ?? detail?.title ?? "Something unusual is happening on Maya’s account"}.`.replace(/\.\.$/, "."),
    2: call && firstRisk
      ? firstRisk.type === "protection.changed"
        ? `Maya just turned off ${String((firstRisk.data as Record<string, unknown>).name ?? "a protection").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())} during that call.`
        : `Maya just ${firstRisk.type === "transfer_pin.requested" ? "requested a Transfer PIN" : lower(markerLabel(firstRisk))} during that call.`
      : "Something risky just happened on Maya’s account.",
    3:
      done.some((a) => a.kind === "relock") && done.some((a) => a.kind === "hold_transfer_pin")
        ? "Titan stepped in: protection is back on, the PIN is held."
        : done.length
          ? `Titan stepped in: ${lower(done[0].description).replace(/\.$/, "")}.`
          : "Titan is stepping in to protect Maya’s account.",
    4: "Maya is safe. Titan is watching her account for 24 hours.",
  }[stage];

  const stepState = (n: Stage): StoryStep["state"] => (n < stage ? "done" : n === stage ? (stage === 4 ? "done" : "now") : "next");
  const steps: StoryStep[] = [
    {
      n: 1,
      title: call ? "Suspicious call" : "Something unusual",
      line: call
        ? `“${call.caller_name ?? "Unknown caller"}” · ${call.attestation === "A" ? "verified" : "unverified"} caller ID · 0:00`
        : `${detail?.title ?? "Account activity"} · 0:00`,
      state: stepState(1),
    },
    {
      n: 2,
      title: call ? "Risky change mid-call" : "Risky change",
      line: firstRisk
        ? `${risky.map((m) => markerLabel(m)).slice(0, 2).join(", then ")} · ${at(base, firstRisk.ts)}`
        : topReason ?? "Watching what happens next",
      state: stepState(2),
    },
    {
      n: 3,
      title: "Titan steps in",
      line: done.length
        ? `${done.slice(0, 2).map(short).join(", ")} · ${at(base, done[0].created_at)}`
        : "Scoring the risk and checking every claim",
      state: stepState(3),
    },
    {
      n: 4,
      title: "Recovered with Maya",
      line:
        stage === 4
          ? mayaApproved.length
            ? `Maya approved ${mayaApproved.length} ${mayaApproved.length === 1 ? "fix" : "fixes"} · watching for 24 h`
            : "Watching her account for 24 hours"
          : "She approves each fix by text",
      state: stepState(4),
    },
  ];

  const { items, deliveredId } = threadOf(detail?.messages ?? []);
  const end = stage === 4 && detail ? ms(detail.updated_at) : now;
  const clock = base === null ? 0 : Math.max(0, (Math.min(now, end) - base) / 1000);

  return {
    stage,
    headline,
    steps,
    thread: items,
    deliveredId,
    typing: !view.done && view.activeAgent === "response",
    chip: stage === 4 ? "Safe · watching 24 h" : `In progress · ${formatDuration(clock)}`,
    chipTone: stage === 4 ? "safe" : "live",
    clock,
  };
}

/** The bottom strip: how the four agents decided, in one line. */
export function decidedOf(detail: C.CaseDetail | null, view: GuardianView) {
  const risk = detail?.risk ?? null;
  const v = detail?.verification ?? null;
  return [
    { label: "Context", value: "", ok: view.columns.context.length > 0 && (view.columns.risk.length > 0 || view.done) },
    { label: "Risk", value: risk ? `${Math.round(risk.probability * 100)}%` : "", ok: !!risk },
    { label: "Verifier", value: v ? `${v.claims_checked - v.claims_dropped}/${v.claims_checked}` : "", ok: v?.status === "verified" },
    { label: "Response", value: "", ok: view.done },
  ];
}
