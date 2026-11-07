"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { TGlyph } from "@/components/TGlyph";
import type { Contract as C } from "@/lib/api/client";

type Props = {
  screen: NonNullable<C.CheckResponse["pause_screen"]>;
  reasons: string[];
  busy: "help" | "continue" | null;
  onHelp: () => void;
  onContinue: () => void;
};

// The most important screen: Titan stops Maya mid-flow. Copy comes from the brain (gate.py), not the UI.
export function PauseScreen({ screen, reasons, busy, onHelp, onContinue }: Props) {
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => title.current?.focus(), []);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center overflow-y-auto overscroll-contain bg-[rgb(20_20_20/0.55)] p-4">
      <section
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="pause-title"
        aria-describedby="pause-body"
        className="pause-in w-full max-w-2xl rounded-2xl bg-surface p-7 shadow-[0_24px_60px_rgb(0_0_0/0.25)] sm:p-10"
      >
        <div className="flex items-center gap-3 text-ink-2">
          <TGlyph size={32} />
          <span className="text-body font-semibold">Titan</span>
        </div>
        <h2 id="pause-title" ref={title} tabIndex={-1} className="mt-6 text-[clamp(28px,4vw,36px)] font-bold leading-tight tracking-tight outline-none">
          {screen.title}
        </h2>
        <p id="pause-body" className="mt-4 text-lead text-ink-2">
          {screen.body}
        </p>
        {reasons.length > 0 && (
          <ul className="mt-6 flex flex-col gap-2 rounded-xl bg-surface-2 p-5 text-body">
            {reasons.map((r) => (
              <li key={r} className="flex gap-3">
                <span aria-hidden className="mt-[10px] h-2 w-2 flex-none rounded-full bg-accent" />
                {r}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-8 flex flex-col gap-3">
          <button
            type="button"
            onClick={onHelp}
            disabled={busy !== null}
            className="min-h-16 rounded-full bg-accent px-8 text-lead font-semibold text-accent-ink transition-[transform,opacity] hover:opacity-90 active:scale-[0.98] disabled:opacity-60"
          >
            {busy === "help" ? "Getting Titan…" : screen.help_label}
          </button>
          <button
            type="button"
            onClick={onContinue}
            disabled={busy !== null}
            className="min-h-14 rounded-full border border-line-strong bg-surface px-8 text-body font-semibold transition-colors hover:bg-surface-2 disabled:opacity-60"
          >
            {busy === "continue" ? "One moment…" : screen.continue_label}
          </button>
        </div>
      </section>
    </div>
  );
}

export function CallingScreen({ caseId, onClose }: { caseId: string | null; onClose: () => void }) {
  const title = useRef<HTMLHeadingElement>(null);
  useEffect(() => title.current?.focus(), []);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center overflow-y-auto overscroll-contain bg-[rgb(20_20_20/0.55)] p-4">
      <section
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="calling-title"
        className="pause-in w-full max-w-2xl rounded-2xl bg-surface p-7 shadow-[0_24px_60px_rgb(0_0_0/0.25)] sm:p-10"
      >
        <TGlyph size={44} />
        <h2 id="calling-title" ref={title} tabIndex={-1} className="mt-6 text-[clamp(28px,4vw,36px)] font-bold leading-tight tracking-tight outline-none">
          Titan is calling you now.
        </h2>
        <p className="mt-4 text-lead text-ink-2">
          Your protection stays on. You can hang up on the other call. Titan will never ask for a PIN or a code.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          {caseId && (
            <Link
              href={`/case/${encodeURIComponent(caseId)}`}
              className="inline-flex min-h-14 items-center justify-center rounded-full bg-ink px-8 text-lead font-semibold text-surface transition-[transform,opacity] hover:opacity-90 active:scale-[0.98]"
            >
              See what Titan is doing
            </Link>
          )}
          <button
            type="button"
            onClick={onClose}
            className="min-h-14 rounded-full border border-line-strong bg-surface px-8 text-body font-semibold transition-colors hover:bg-surface-2"
          >
            Back to my account
          </button>
        </div>
      </section>
    </div>
  );
}
