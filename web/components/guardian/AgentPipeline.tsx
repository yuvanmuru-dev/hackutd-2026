"use client";

import { Fragment, useEffect, useRef } from "react";
import type { Contract as C } from "@/lib/api/client";
import { PIPELINE, type GuardianView, type PipelineAgent } from "./derive";

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

/** Steps shown per agent: a projector reads two lines a column, not eight. */
const SHOWN = 2;

type StageState = "idle" | "active" | "done";

function stageState(view: GuardianView, agent: PipelineAgent): StageState {
  const steps = view.columns[agent];
  if (steps.length === 0) return "idle";
  if (view.activeAgent === agent) return "active";
  return "done";
}

export function AgentPipeline({ view }: { view: GuardianView }) {
  return (
    <section aria-label="Four agents, in order" className="grid min-h-0 grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:grid-rows-[minmax(0,1fr)] lg:gap-4">
      {PIPELINE.map((p, i) => {
        const state = stageState(view, p.agent);
        const steps = view.columns[p.agent];
        return (
          <Fragment key={p.agent}>
            <article className="g-panel g-stage px-4 py-4 2xl:px-5" data-state={state} aria-current={state === "active" ? "step" : undefined}>
              <header className="flex items-center gap-3">
                <span className="g-stage-num" aria-hidden>
                  {state === "done" ? <svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="m3.5 8.5 3 3 6-7" /></svg> : i + 1}
                </span>
                <div className="min-w-0">
                  <h2 className="text-[20px] font-semibold leading-tight">{p.label}</h2>
                  <p className="g-label">
                    {p.job}
                    {state === "active" ? " · working" : state === "done" ? ` · ${steps.length} ${steps.length === 1 ? "step" : "steps"}` : ""}
                  </p>
                </div>
              </header>
              <StepList steps={steps}>
                {steps.length === 0 && (
                  <li className="text-[var(--g-ink-3)]">{view.done ? "Not needed for this case" : "Waiting"}</li>
                )}
                {steps.length > SHOWN && (
                  <li className="g-label">
                    {steps.length - SHOWN} earlier {steps.length - SHOWN === 1 ? "step" : "steps"}
                  </li>
                )}
                {steps.slice(-SHOWN).map((s) => (
                  <li key={s.seq} className="g-step" data-type={s.type}>
                    <p className="g-step-title leading-snug">
                      <span className="g-step-kind">{KIND[s.type] ?? s.type} </span>
                      {s.title}
                    </p>
                  </li>
                ))}
              </StepList>
            </article>
          </Fragment>
        );
      })}
    </section>
  );
}

/** Keeps the newest step in view as the stream appends to a column. */
function StepList({ steps, children }: { steps: C.StepEvent[]; children: React.ReactNode }) {
  const ref = useRef<HTMLOListElement>(null);
  const first = useRef(true);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Jump on first paint, glide for steps that arrive later; wait a frame so the new row has its height.
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const behavior: ScrollBehavior = first.current || reduce ? "auto" : "smooth";
    first.current = false;
    const id = requestAnimationFrame(() => el.scrollTo({ top: el.scrollHeight, behavior }));
    return () => cancelAnimationFrame(id);
  }, [steps.length]);
  return (
    <ol ref={ref} className="g-scroll mt-3 flex max-h-[320px] min-h-0 flex-1 flex-col divide-y divide-[var(--g-line)] lg:max-h-none [&>li]:py-2">
      {children}
    </ol>
  );
}
