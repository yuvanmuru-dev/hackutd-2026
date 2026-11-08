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

const CHANNEL: Record<string, string> = { imessage: "iMessage", sms: "SMS", voice: "Phone call", web: "Web" };

const SHOWN = 2;

const time = (ts: string) =>
  new Date(ts).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });

export function ConversationStrip({ messages }: { messages: C.Message[] }) {
  const box = useRef<HTMLDivElement>(null);
  const first = useRef(true);
  const sorted = [...messages].sort((a, b) => a.ts.localeCompare(b.ts));
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const behavior: ScrollBehavior = first.current || reduce ? "auto" : "smooth";
    first.current = false;
    const id = requestAnimationFrame(() => el.scrollTo({ top: el.scrollHeight, behavior }));
    return () => cancelAnimationFrame(id);
  }, [messages.length]);

  return (
    <section className="g-panel flex min-h-0 flex-col px-6 py-5" aria-label="Messages and call">
      <h2 className="text-[20px] font-semibold">Messages and call</h2>
      <div ref={box} className="g-scroll mt-2 flex max-h-[360px] min-h-0 flex-1 flex-col pr-1 lg:max-h-none" aria-live="polite">
        {sorted.length === 0 && <p className="text-[var(--g-ink-3)]">Nothing sent to Maya yet</p>}
        {sorted.length > SHOWN && (
          <p className="g-label pb-1">
            {sorted.length - SHOWN} earlier {sorted.length - SHOWN === 1 ? "message" : "messages"}
          </p>
        )}
        {sorted.slice(-SHOWN).map((m) => {
          const who = m.direction === "out" ? "Titan" : "Maya";
          const kind = m.direction === "out" && m.channel !== "voice" ? KIND[m.kind] ?? m.kind : null;
          return (
            <div key={m.message_id} className="g-msg" data-dir={m.direction}>
              <p className="g-msg-who">
                {who} · {CHANNEL[m.channel] ?? m.channel}
                <span className="block font-medium text-[var(--g-ink-3)] tabular">
                  {time(m.ts)}
                  {kind ? ` · ${kind}` : ""}
                </span>
              </p>
              <p className={m.channel === "voice" ? "text-[var(--g-ink-2)]" : undefined}>
                {m.channel === "voice" ? `“${m.text.replace(/^Titan:\s*/, "")}”` : m.text.replace(/^Titan:\s*/, "")}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
