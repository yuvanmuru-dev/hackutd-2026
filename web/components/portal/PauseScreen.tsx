"use client";

import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";
import { TGlyph, Wordmark } from "@/components/TGlyph";
import { BTN_DARK, BTN_PRIMARY, BTN_SECONDARY, LABEL } from "@/components/ui";
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
      className="m-0 h-dvh max-h-dvh w-full max-w-none overflow-y-auto overscroll-contain border-t-4 border-accent bg-surface p-6 text-ink backdrop:bg-[rgb(20_20_20/0.72)] sm:m-auto sm:h-fit sm:max-h-[calc(100dvh-4rem)] sm:w-[calc(100%-2rem)] sm:max-w-[560px] sm:rounded-panel sm:p-8 sm:shadow-float"
    >
      {children}
    </dialog>
  );
}

// A carrier security interstitial: full-bleed sheet on a phone, a 560px panel with T-Mobile's magenta top rule on
// a desktop. No entrance animation; the only shadow in the app is here, because the dialog floats.
const TITLE = "text-balance text-[clamp(24px,3vw,30px)] font-bold leading-tight tracking-[-0.01em] outline-none";

function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-center gap-3">
      <TGlyph size={28} title="" />
      <span className={LABEL}>{children}</span>
    </p>
  );
}

function Footer() {
  return (
    <p className="mt-6 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-line pt-4 text-[15px] text-ink-3">
      <span>Nothing has changed. Your protection is on.</span>
      <Wordmark size={16} />
    </p>
  );
}

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
      <Eyebrow>Security check</Eyebrow>
      <h2 id="pause-title" tabIndex={-1} className={`mt-5 ${TITLE}`}>
        {screen.title}
      </h2>
      <p id="pause-body" className="mt-3 text-body text-ink">
        {screen.body}
      </p>
      {reasons.length > 0 && (
        <>
          <p className={`mt-6 ${LABEL}`}>What we noticed</p>
          <ul className="mt-1 divide-y divide-line border-y border-line text-body">
            {reasons.map((r) => (
              <li key={r} className="py-2.5">
                {r}
              </li>
            ))}
          </ul>
        </>
      )}
      <div className="mt-8 flex flex-col gap-3">
        <button type="button" onClick={onHelp} disabled={busy !== null} className={`${BTN_PRIMARY} h-14 w-full text-lead`}>
          {busy === "help" ? "Connecting you to Titan…" : screen.help_label}
        </button>
        <button type="button" onClick={onContinue} disabled={busy !== null} className={`${BTN_SECONDARY} h-14 w-full`}>
          {busy === "continue" ? "One moment…" : screen.continue_label}
        </button>
      </div>
      <Footer />
    </Modal>
  );
}

export function CallingScreen({ caseId, onClose }: { caseId: string | null; onClose: () => void }) {
  return (
    <Modal labelledBy="calling-title" describedBy="calling-body">
      <Eyebrow>Help is on the way</Eyebrow>
      <h2 id="calling-title" tabIndex={-1} className={`mt-5 ${TITLE}`}>
        Titan is calling you now
      </h2>
      <p id="calling-body" className="mt-3 text-body text-ink">
        Your protection is still on. You can hang up on the other call. Titan will never ask you for a PIN or a code.
      </p>
      <div className="mt-8 flex flex-col gap-3">
        {caseId && (
          <Link href={`/case/${encodeURIComponent(caseId)}`} className={`${BTN_DARK} h-14 w-full`}>
            See what Titan is doing
          </Link>
        )}
        <button type="button" onClick={onClose} className={`${BTN_SECONDARY} h-14 w-full`}>
          Back to my account
        </button>
      </div>
    </Modal>
  );
}
