// The guardian screen's story: one question ("what's happening to Maya, and what did Titan do?") answered
// from the same CaseDetail + steps the brain streams. Pure functions, no fetch.
//
// No clock on the steps or the chip: the brain's own texts (reasons, summaries) count time from the
// recorded call, so a second clock in the UI would disagree with them. The one duration shown is Titan's
// own call to Maya, measured from its transcript lines.
import type { Contract as C } from "@/lib/api/client";
import { formatDuration, isRiskyMarker, markerLabel, productCase, wordsFor, type GuardianView } from "./derive";

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
  chipTone: "live" | "safe";
}

const ms = (iso: string) => Date.parse(iso);

/** Short, projector-sized names for what Titan did (lower case: they follow a "·"). */
const SHORT: Partial<Record<C.Action["kind"], string>> = {
  relock: "protection back on",
  hold_transfer_pin: "PIN held",
  require_step_up: "extra checks on",
  reset_pin: "account PIN reset",
  revoke_transfer_pin: "Transfer PIN cancelled",
  sign_out_sessions: "other devices signed out",
  report_number: "number reported",
};
const short = (a: C.Action) => SHORT[a.kind] ?? productCase(a.description.charAt(0).toLowerCase() + a.description.slice(1));

/** Every message as the brain sent it, one bubble each (the brain keeps texts short); Titan's call is one row. */
function threadOf(messages: C.Message[]): { items: ThreadItem[]; deliveredId: string | null } {
  const sorted = [...messages].sort((a, b) => a.ts.localeCompare(b.ts));
  const items: ThreadItem[] = [];
  let deliveredId: string | null = null;
  for (let i = 0; i < sorted.length; i++) {
    const m = sorted[i];
    if (m.channel === "voice") {
      let j = i;
      while (j + 1 < sorted.length && sorted[j + 1].channel === "voice") j++;
      const secs = Math.max(1, (ms(sorted[j].ts) - ms(m.ts)) / 1000 + 8);
      items.push({ kind: "call", id: m.message_id, text: `Titan called Maya · ${formatDuration(secs)}` });
      i = j;
      continue;
    }
    const from = m.direction === "out" ? "titan" : "maya";
    // The sender is the bubble's side, so a leading "Titan:" label is dropped; the words are the brain's.
    items.push({ kind: "bubble", id: m.message_id, from, text: productCase(m.text.replace(/^Titan\s*:\s*/, "")) });
    if (from === "maya") deliveredId = m.message_id;
  }
  return { items, deliveredId };
}

export function storyOf(detail: C.CaseDetail | null, head: C.Case | null, view: GuardianView): Story {
  const status = head?.status ?? detail?.status ?? "open";
  const call = detail?.call ?? null;
  const risky = view.callMarkers.filter(isRiskyMarker);
  const actions = detail?.actions ?? [];
  const done = actions.filter((a) => a.status === "applied" || a.status === "approved");
  const mayaApproved = actions.filter((a) => a.requires_approval && (a.status === "applied" || a.status === "approved"));
  const responding = view.columns.response.length > 0;
  const risk = detail?.risk ?? null;

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
  const topReason = risk?.top_reasons.find((r) => r.contribution > 0)?.text ?? null;

  const headline = {
    1: call
      ? claimsCarrier
        ? "A caller claiming to be T-Mobile is on the line with Maya."
        : "An unverified caller is on the line with Maya."
      : `${head?.title ?? detail?.title ?? "Something unusual is happening on Maya’s account"}.`.replace(/\.\.$/, "."),
    2: call && firstRisk
      ? `Maya just ${firstRisk.type === "protection.changed" ? `turned off ${markerLabel(firstRisk).replace(/ off$/, "")}` : firstRisk.type === "transfer_pin.requested" ? "requested a Transfer PIN" : markerLabel(firstRisk).toLowerCase()} during that call.`
      : "Something risky just happened on Maya’s account.",
    3:
      done.some((a) => a.kind === "relock") && done.some((a) => a.kind === "hold_transfer_pin")
        ? "Titan stepped in: protection is back on, the PIN is held."
        : done.length
          ? `Titan stepped in: ${short(done[0])}.`
          : "Titan is stepping in to protect Maya’s account.",
    4: "Maya is safe. Titan is watching her account for 24 hours.",
  }[stage];

  const stepState = (n: Stage): StoryStep["state"] =>
    n < stage ? "done" : n === stage ? (stage === 4 ? "done" : "now") : "next";

  const verdict = risk ? `${wordsFor(risk.threat)} · ${Math.round(risk.probability * 100)}%` : null;
  const steps: StoryStep[] = [
    {
      n: 1,
      title: call ? "Suspicious call" : "Something unusual",
      line: call
        ? `“${call.caller_name ?? "Unknown caller"}” · ${call.attestation === "A" ? "verified" : "unverified"} caller ID`
        : productCase(detail?.title ?? "Unusual account activity"),
      state: stepState(1),
    },
    {
      n: 2,
      title: call ? "Risky change mid-call" : "Risky change",
      line: firstRisk
        ? risky
            .map((m) => markerLabel(m))
            .slice(0, 2)
            .join(", then ")
        : topReason
          ? productCase(topReason)
          : "Watching what happens next",
      state: stepState(2),
    },
    {
      n: 3,
      title: "Titan steps in",
      line: [verdict, done.length ? done.slice(0, 2).map(short).join(", ") : verdict ? null : "Scoring the risk"]
        .filter(Boolean)
        .join(" · "),
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
  return {
    stage,
    headline,
    steps,
    thread: items,
    deliveredId,
    typing: !view.done && view.activeAgent === "response",
    chip: stage === 4 ? "Safe · watching 24 h" : "In progress",
    chipTone: stage === 4 ? "safe" : "live",
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
