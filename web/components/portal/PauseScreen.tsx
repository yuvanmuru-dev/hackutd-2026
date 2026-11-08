"use client";

import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";
import { Wordmark } from "@/components/TGlyph";
import type { Contract as C } from "@/lib/api/client";

/**
 * Native modal <dialog>: showModal() makes the page behind inert, keeps Tab inside, and gives the
 * ::backdrop. Escape is cancelled on purpose: the pause must be answered, not dismissed.
 */
function Modal({ labelledBy, describedBy, children }: { labelledBy: string; describedBy?: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
    document.getElementById(labelledBy)?.focus();
    return () => d?.close();
  }, [labelledBy]);
  return (
    <dialog
      ref={ref}
      role="alertdialog"
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      onCancel={(e) => e.preventDefault()}
      className="pause-in m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-2xl overflow-y-auto overscroll-contain rounded-2xl bg-surface p-7 text-ink shadow-[0_24px_60px_rgb(0_0_0/0.25)] backdrop:bg-[rgb(17_17_20/0.6)] sm:p-10"
    >
      {children}
    </dialog>
  );
}

const TITLE = "text-balance text-[clamp(28px,4vw,36px)] font-bold leading-tight tracking-[-0.02em] outline-none";
const PRIMARY =
  "inline-flex min-h-16 items-center justify-center rounded-full px-8 text-center text-lead font-semibold transition-[transform,background-color,opacity] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60";
const SECONDARY =
  "inline-flex min-h-14 items-center justify-center rounded-full border border-control bg-surface px-8 text-center text-body font-semibold transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-60";

type Props = {
  screen: NonNullable<C.CheckResponse["pause_screen"]>;
  reasons: string[];
  busy: "help" | "continue" | null;
  onHelp: () => void;
  onContinue: () => void;
};

// The most important screen: Titan stops Maya mid-flow. Copy comes from the brain (gate.py), not the UI.
export function PauseScreen({ screen, reasons, busy, onHelp, onContinue }: Props) {
  return (
    <Modal labelledBy="pause-title" describedBy="pause-body">
      <div className="text-ink-2">
        <Wordmark size={30} />
      </div>
      <h2 id="pause-title" tabIndex={-1} className={`mt-6 ${TITLE}`}>
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
          className={`${PRIMARY} bg-accent text-accent-ink hover:bg-accent-hover`}
        >
          {busy === "help" ? "Getting Titan…" : screen.help_label}
        </button>
        <button type="button" onClick={onContinue} disabled={busy !== null} className={SECONDARY}>
          {busy === "continue" ? "One moment…" : screen.continue_label}
        </button>
      </div>
    </Modal>
  );
}

export function CallingScreen({ caseId, onClose }: { caseId: string | null; onClose: () => void }) {
  return (
    <Modal labelledBy="calling-title" describedBy="calling-body">
      <Wordmark size={30} />
      <h2 id="calling-title" tabIndex={-1} className={`mt-6 ${TITLE}`}>
        Titan is calling you now.
      </h2>
      <p id="calling-body" className="mt-4 text-lead text-ink-2">
        Your protection stays on. You can hang up on the other call. Titan will never ask for a PIN or a code.
      </p>
      <div className="mt-8 flex flex-col gap-3">
        {caseId && (
          <Link href={`/case/${encodeURIComponent(caseId)}`} className={`${PRIMARY} bg-ink text-surface hover:opacity-90`}>
            See what Titan is doing
          </Link>
        )}
        <button type="button" onClick={onClose} className={SECONDARY}>
          Back to my account
        </button>
      </div>
    </Modal>
  );
}
