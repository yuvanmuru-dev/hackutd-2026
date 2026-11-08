"use client";

import "./guardian.css";
import Image from "next/image";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { deriveView } from "./derive";
import { DetailDrawer } from "./DetailDrawer";
import { decidedOf, storyOf, type StoryStep, type ThreadItem } from "./story";
import { useGuardianCase } from "./useGuardianCase";

/** Keeps the thread scrolled to the newest message, as a phone does. */
function usePinnedBottom(count: number) {
  const box = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = box.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [count]);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => (el.scrollTop = el.scrollHeight));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return box;
}

// Judges' projector screen, 1920x1080, light. It answers one question in five seconds:
// what's happening to Maya, and what did Titan do? Details (agents, data used, reasons) live behind D.
export function GuardianScreen({ caseId }: { caseId: string | null }) {
  const { detail, head, steps, mode } = useGuardianCase(caseId);
  const view = useMemo(() => deriveView(detail, steps), [detail, steps]);
  const [drawer, setDrawer] = useState(false);
  const closeDrawer = useCallback(() => setDrawer(false), []);
  const story = storyOf(detail, head, view);
  const decided = decidedOf(detail, view);
  const caseNo = (head?.case_number ?? detail?.case_number ?? "").replace(/^[A-Z]+-/, "");
  const name = detail?.user.name ?? "Maya";

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      if (e.key === "d" || e.key === "D") setDrawer((o) => !o);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const box = usePinnedBottom(story.thread.length + (story.typing ? 1 : 0));
  const thread = story.thread;

  return (
    <main className="guardian g-screen">
      <header className="g-top">
        <Image src="/brand/titan.png" alt="Titan" width={154} height={48} priority className="h-12 w-auto" />
        <span className="g-rule" aria-hidden />
        <span className="g-meta">
          Case {caseNo || "…"} · {name}
        </span>
        {mode === "replay" && <span className="g-meta">Recorded run</span>}
        <span className="g-chip" data-tone={story.chipTone}>
          <span className="g-chip-dot" aria-hidden />
          {story.chip}
        </span>
      </header>

      <h1 key={story.stage} className="g-headline" aria-live="polite">
        {detail ? story.headline : "Loading the case…"}
      </h1>

      <div className="g-body">
        <ol className="g-story" aria-label="What happened, step by step">
          {story.steps.map((s) => (
            <Step key={s.n} step={s} />
          ))}
        </ol>

        <section className="g-phone" aria-label="iMessage thread between Titan and Maya">
          <div className="g-phone-head">
            <span className="g-avatar" aria-hidden>
              <Image src="/brand/titan-t.png" alt="" width={24} height={27} className="h-[27px] w-auto" />
            </span>
            <span className="g-phone-title">iMessage · Titan</span>
          </div>
          <div ref={box} className="g-thread" aria-live="polite">
            {thread.length === 0 && !story.typing && <p className="g-sys">No messages yet</p>}
            {thread.map((m) => (
              <Item key={m.id} item={m} delivered={m.id === story.deliveredId} />
            ))}
            {story.typing && (
              <span className="g-bubble g-typing" data-from="titan" role="status" aria-label="Titan is typing">
                <span />
                <span />
                <span />
              </span>
            )}
          </div>
        </section>
      </div>

      <footer className="g-strip">
        <span className="g-strip-lead">How Titan decided</span>
        <ol className="g-decided" aria-label="The four agents">
          {decided.map((d, i) => (
            <li key={d.label}>
              {i > 0 && (
                <svg aria-hidden width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="m5 2 5 5-5 5" />
                </svg>
              )}
              <span>
                {d.label}
                {d.value ? ` ${d.value}` : ""}
              </span>
              {d.ok && (
                <svg aria-label="done" role="img" width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="var(--g-positive)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                  <path d="m3.5 9.5 3.5 3.5 7.5-8" />
                </svg>
              )}
            </li>
          ))}
        </ol>
        <span>Nemotron · self-hosted on Brev</span>
        <span>Risk model: {detail?.risk?.model ?? "…"}</span>
        <button type="button" className="g-key" onClick={() => setDrawer(true)} aria-keyshortcuts="D">
          Details <kbd>D</kbd>
        </button>
      </footer>

      {drawer && <DetailDrawer detail={detail} head={head} view={view} onClose={closeDrawer} />}
    </main>
  );
}

function Step({ step }: { step: StoryStep }) {
  return (
    <li className="g-step-row" data-state={step.state} aria-current={step.state === "now" ? "step" : undefined}>
      <span className="g-num" aria-hidden>
        {step.state === "done" ? (
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12.5l4.5 4.5L19 7.5" />
          </svg>
        ) : (
          step.n
        )}
      </span>
      <div className="min-w-0">
        <p className="g-row-title">
          {step.title}
          {step.state === "done" && <span className="sr-only"> (done)</span>}
          {step.state === "now" && <span className="sr-only"> (happening now)</span>}
        </p>
        <p className="g-row-line">{step.line}</p>
      </div>
    </li>
  );
}

function Item({ item, delivered }: { item: ThreadItem; delivered: boolean }) {
  if (item.kind === "call") return <p className="g-sys">{item.text}</p>;
  return (
    <>
      <p className="g-bubble" data-from={item.from}>
        <span className="sr-only">{item.from === "titan" ? "Titan: " : "Maya: "}</span>
        {item.text}
      </p>
      {delivered && <p className="g-delivered">Delivered</p>}
    </>
  );
}
