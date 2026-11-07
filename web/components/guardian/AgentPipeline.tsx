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

type StageState = "idle" | "active" | "done";

function stageState(view: GuardianView, agent: PipelineAgent): StageState {
  const steps = view.columns[agent];
  if (steps.length === 0) return "idle";
  if (view.activeAgent === agent) return "active";
  return "done";
}

export function AgentPipeline({ view }: { view: GuardianView }) {
  return (
    <section aria-label="Four agents, in order" className="grid min-h-0 grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto_minmax(0,1fr)_auto_minmax(0,1fr)] grid-rows-[minmax(0,1fr)] gap-2">
      {PIPELINE.map((p, i) => {
        const state = stageState(view, p.agent);
        const steps = view.columns[p.agent];
        const next = PIPELINE[i + 1];
        return (
          <Fragment key={p.agent}>
            <article className="g-panel g-stage px-4 py-4 2xl:px-5" data-state={state} aria-current={state === "active" ? "step" : undefined}>
              <header className="flex items-center gap-3">
                <span className="g-stage-num" aria-hidden>
                  {state === "done" ? "✓" : i + 1}
                </span>
                <div className="min-w-0">
                  <h2 className="text-[26px] font-bold leading-tight tracking-tight">{p.label}</h2>
                  <p className="g-label">
                    {p.job}
                    {state === "active" ? " · working" : state === "done" ? ` · ${steps.length} ${steps.length === 1 ? "step" : "steps"}` : ""}
                  </p>
                </div>
              </header>
              <StepList steps={steps}>
                {steps.length === 0 && <li className="text-[var(--g-ink-3)]">Waiting for its turn</li>}
                {steps.map((s) => (
                  <li key={s.seq} className="g-step" data-type={s.type}>
                    <span className="g-step-kind">{KIND[s.type] ?? s.type}</span>
                    <p className="g-step-title leading-snug">{s.title}</p>
                  </li>
                ))}
              </StepList>
            </article>
            {next && (
              <span className="g-arrow" data-lit={view.columns[next.agent].length > 0} aria-hidden>
                →
              </span>
            )}
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
    const behavior: ScrollBehavior = first.current ? "auto" : "smooth";
    first.current = false;
    const id = requestAnimationFrame(() => el.scrollTo({ top: el.scrollHeight, behavior }));
    return () => cancelAnimationFrame(id);
  }, [steps.length]);
  return (
    <ol ref={ref} className="g-scroll mt-4 flex min-h-0 flex-1 flex-col gap-3">
      {children}
    </ol>
  );
}
