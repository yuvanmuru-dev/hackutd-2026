"use client";

import { useEffect, useRef } from "react";
import type { Contract as C } from "@/lib/api/client";

const KIND: Partial<Record<C.Message["kind"], string>> = {
  heads_up: "Heads-up",
  alert: "Alert",
  question: "Question",
  summary: "Incident summary",
  recovery_step: "Recovery step",
  info: "Info",
  reply: "Reply",
};

const time = (ts: string) =>
  new Date(ts).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });

export function ConversationStrip({ messages }: { messages: C.Message[] }) {
  const box = useRef<HTMLDivElement>(null);
  const first = useRef(true);
  const sorted = [...messages].sort((a, b) => a.ts.localeCompare(b.ts));
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const behavior: ScrollBehavior = first.current ? "auto" : "smooth";
    first.current = false;
    const id = requestAnimationFrame(() => el.scrollTo({ top: el.scrollHeight, behavior }));
    return () => cancelAnimationFrame(id);
  }, [messages.length]);

  return (
    <section className="g-panel flex min-h-0 flex-col px-6 py-5" aria-label="Messages and call">
      <h2 className="text-[22px] font-semibold">iMessage and Titan’s call</h2>
      <div ref={box} className="g-scroll mt-3 flex min-h-0 flex-1 flex-col gap-3 pr-1" aria-live="polite">
        {sorted.length === 0 && <p className="text-[var(--g-ink-3)]">Nothing sent to Maya yet</p>}
        {sorted.map((m) =>
          m.channel === "voice" ? (
            <p key={m.message_id} className="g-step leading-snug">
              <span className="font-semibold" style={{ color: m.direction === "out" ? "var(--g-accent)" : "var(--g-ink)" }}>
                {m.direction === "out" ? "Titan on the phone" : "Maya"}:
              </span>{" "}
              <span className="text-[var(--g-ink-2)]">“{m.text.replace(/^Titan:\s*/, "")}”</span>
            </p>
          ) : (
            <div key={m.message_id} className="flex flex-col">
              <span
                className="g-label tabular"
                style={{ alignSelf: m.direction === "out" ? "flex-end" : "flex-start" }}
              >
                {m.direction === "out" ? `Titan · ${KIND[m.kind] ?? m.kind}` : "Maya"} · {time(m.ts)}
              </span>
              <p className="g-bubble mt-1" data-dir={m.direction}>
                {m.text.replace(/^Titan:\s*/, "")}
              </p>
            </div>
          ),
        )}
      </div>
    </section>
  );
}
