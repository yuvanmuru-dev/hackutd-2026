"use client";

import { useEffect, useRef } from "react";
import type { Contract as C } from "@/lib/api/client";
import { confidenceWords, PIPELINE, productCase, wordsFor, type GuardianView, type PipelineAgent } from "./derive";

type Props = { detail: C.CaseDetail | null; head: C.Case | null; view: GuardianView; onClose: () => void };

/** The label above each step: what kind of step it was. */
const KIND: Partial<Record<C.StepEvent["type"], string>> = {
  plan: "Plan",
  tool_call: "Calls",
  tool_result: "Found",
  signal: "Signal",
  score: "Score",
  verify: "Checked",
  action: "Did",
  message: "Sent",
  call: "Calling",
  approval_needed: "Asks",
  approved: "Approved",
  summary: "Wrote",
  error: "Guardrail",
};

/** Which NVIDIA model answered, in words a judge recognises. The model id comes from the step's data. */
export function modelWords(id: string | null | undefined): string | null {
  if (!id) return null;
  const m = id.toLowerCase();
  if (m.includes("nemotron-nano")) return "Nemotron Nano · on our Brev GPU";
  if (m.includes("ultra")) return "Nemotron 3 Ultra";
  if (m.includes("lightning")) return "Nemotron 3.5 Lightning · hosted";
  if (m.includes("safety-guard")) return "Nemotron Safety Guard";
  return id.replace(/^nvidia\//, "");
}

const modelOf = (s: C.StepEvent): string | null => {
  const d = (s.data ?? {}) as Record<string, unknown>;
  return typeof d.model === "string" ? d.model : null;
};

/** The newest model id among these steps. */
const lastModel = (steps: C.StepEvent[]) => [...steps].reverse().map(modelOf).find((m) => m !== null) ?? null;

/** One line per agent: what it did, from its own steps. */
function didOf(agent: PipelineAgent, steps: C.StepEvent[], all: C.StepEvent[], detail: C.CaseDetail | null): string {
  if (steps.length === 0) return "Not needed for this case";
  if (agent === "context") {
    const tools = steps.filter((s) => s.type === "tool_call").length;
    const facts = steps.filter((s) => s.type === "tool_result" || s.type === "signal").length;
    return `${tools} ${tools === 1 ? "tool" : "tools"} · ${facts} ${facts === 1 ? "fact" : "facts"}`;
  }
  if (agent === "risk") {
    const r = detail?.risk;
    return r ? `${wordsFor(r.threat)} · ${Math.round(r.probability * 100)}%` : productCase(steps[steps.length - 1].title);
  }
  if (agent === "verifier") {
    const v = detail?.verification;
    return v ? `${v.claims_checked - v.claims_dropped} of ${v.claims_checked} claims confirmed` : productCase(steps[steps.length - 1].title);
  }
  const acts = steps.filter((s) => s.type === "action").length;
  const called = steps.some((s) => s.type === "call");
  const wrote = all.some((s) => s.type === "summary");
  return [`${acts} ${acts === 1 ? "action" : "actions"}`, called && "called Maya", wrote && "summary sent"].filter(Boolean).join(" · ");
}

const VIA: Record<NonNullable<C.Action["approved_via"]>, string> = { web: "on the web", sms: "by text", voice: "on the call" };

function actionNote(a: C.Action): string {
  switch (a.status) {
    case "applied":
    case "approved":
      return a.requires_approval ? `Maya approved ${a.approved_via ? VIA[a.approved_via] : ""}`.trim() : "Done automatically";
    case "awaiting_approval":
      return "Waiting for Maya";
    case "proposed":
      return "Proposed";
    case "rejected":
      return "Skipped · Maya said no";
    case "failed":
      return "Didn’t go through";
  }
}

// For the judges who ask "how did it decide?". One scrolling column, three sections:
// the agents (and the model each used), why, and what Titan did + the data it used.
// Opened with D or the Details button; D (the screen's toggle), Esc or Close closes it.
export function DetailDrawer({ detail, head, view, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    // "close" is dispatched as a task, so a close from a re-mount can arrive after the dialog reopened:
    // only a dialog that is really closed means the viewer closed it.
    const closed = () => {
      if (!d.open) onClose();
    };
    d.addEventListener("close", closed);
    if (!d.open) d.showModal();
    return () => {
      d.removeEventListener("close", closed);
      d.close();
    };
  }, [onClose]);

  const risk = detail?.risk ?? null;
  const reasons = (risk?.top_reasons ?? []).filter((r) => r.contribution > 0).slice(0, 3);
  const counter = (risk?.top_reasons ?? []).find((r) => r.contribution < 0);
  const v = detail?.verification ?? null;
  const actions = [...(detail?.actions ?? [])].sort((a, b) => a.created_at.localeCompare(b.created_at));
  const doneN = actions.filter((a) => a.status === "applied" || a.status === "approved").length;
  const skippedN = actions.filter((a) => a.status === "rejected").length;
  const voice = (detail?.messages ?? []).filter((m) => m.channel === "voice").sort((a, b) => a.ts.localeCompare(b.ts));
  // The Response agent speaks through the messaging door; its model rides on those steps.
  const messagingModel = lastModel(view.steps.filter((s) => s.agent === "messaging"));

  return (
    <dialog ref={ref} aria-labelledby="drawer-title" className="g-drawer">
      <div className="g-drawer-head">
        <h2 id="drawer-title" className="g-drawer-title">
          How Titan decided
        </h2>
        <button type="button" className="g-key" onClick={onClose}>
          Close <kbd>D</kbd>
        </button>
      </div>

      <div className="g-drawer-body">
        <section aria-labelledby="d-agents">
          <h3 id="d-agents" className="g-d-h">
            The agents
          </h3>
          <ol className="g-d-list">
            {PIPELINE.map((p) => {
              const steps = view.columns[p.agent];
              const model = modelWords(lastModel(steps) ?? (p.agent === "response" ? messagingModel : null));
              return (
                <li key={p.agent} className="g-d-agent">
                  <p className="g-d-agent-line">
                    <span className="g-d-agent-name">{p.label}</span>
                    <span>{didOf(p.agent, steps, view.steps, detail)}</span>
                    {model && <span className="g-d-model">{model}</span>}
                  </p>
                  {steps.length > 0 && (
                    <ol className="g-d-steps">
                      {steps.map((s) => (
                        <li key={s.seq}>
                          <span className="g-d-kind">{KIND[s.type] ?? s.type}</span>
                          <span className="g-d-text">{productCase(s.title)}</span>
                        </li>
                      ))}
                    </ol>
                  )}
                </li>
              );
            })}
          </ol>
        </section>

        {view.errors.length > 0 && (
          <section aria-labelledby="d-errors">
            <h3 id="d-errors" className="g-d-h">
              What went wrong
            </h3>
            <div className="g-d-card">
              <ul className="g-d-rows">
                {view.errors.map((s) => (
                  <li key={s.seq}>
                    <span className="g-d-kind">{s.agent === "system" ? "Run" : s.agent}</span>
                    <span className="g-d-text">{productCase(s.title)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}

        <section aria-labelledby="d-why">
          <h3 id="d-why" className="g-d-h">
            Why
          </h3>
          <div className="g-d-card">
            <p className="g-d-verdict">{risk ? wordsFor(risk.threat) : "Not scored yet"}</p>
            <p className="g-d-sub">
              {confidenceWords(risk, head)} · risk model {risk?.model ?? "pending"}
            </p>
            {reasons.length > 0 && (
              <ul className="g-d-rows">
                {reasons.map((r) => (
                  <li key={r.feature}>{productCase(r.text)}</li>
                ))}
                {counter && (
                  <li>
                    <span className="g-d-kind">Against it</span>
                    <span className="g-d-text">{productCase(counter.text)}</span>
                  </li>
                )}
              </ul>
            )}
            <p className="g-d-sub">
              {v
                ? `${v.status === "verified" ? "Verified" : "Confidence reduced"} · ${v.claims_checked} claims checked, ${v.claims_dropped} dropped`
                : "Verification pending"}
            </p>
          </div>
        </section>

        <section aria-labelledby="d-did">
          <h3 id="d-did" className="g-d-h">
            What Titan did
          </h3>
          <div className="g-d-card">
            <p className="g-d-sub">
              {doneN} done{skippedN ? ` · ${skippedN} skipped` : ""}
              {actions.some((a) => a.status === "awaiting_approval") ? " · waiting for Maya" : ""}
            </p>
            <ul className="g-d-rows">
              {actions.length === 0 && <li>No actions yet</li>}
              {actions.map((a) => (
                <li key={a.action_id} className="g-d-action" data-status={a.status}>
                  <span className="g-d-mark" aria-hidden>
                    {a.status === "applied" || a.status === "approved" ? (
                      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                        <path d="m4 10.5 4 4 8-9" />
                      </svg>
                    ) : null}
                  </span>
                  <span>
                    <span className="g-d-text">{productCase(a.description)}</span>
                    <span className="g-d-kind g-d-after">{actionNote(a)}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <h3 className="g-d-h">Data used</h3>
          <div className="g-d-card">
            <ul className="g-d-rows">
              {(detail?.data_used ?? []).map((d) => (
                <li key={d}>{productCase(d)}</li>
              ))}
            </ul>
            <p className="g-d-sub">Never used: call audio, location, contacts</p>
          </div>

          {voice.length > 0 && (
            <>
              <h3 className="g-d-h">Titan&rsquo;s call with Maya</h3>
              <div className="g-d-card">
                <ul className="g-d-rows">
                  {voice.map((m) => (
                    <li key={m.message_id}>
                      <span className="g-d-kind">{m.direction === "out" ? "Titan" : "Maya"}</span>
                      <span className="g-d-text">&ldquo;{productCase(m.text.replace(/^Titan\s*:\s*/, ""))}&rdquo;</span>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </section>
      </div>
    </dialog>
  );
}
