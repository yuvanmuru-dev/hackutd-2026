"use client";

import { TGlyph } from "@/components/TGlyph";

// First visit only. Plain words about what the behavior summary is and isn't.
export function ConsentScreen({ onChoose }: { onChoose: (yes: boolean) => void }) {
  return (
    <section
      aria-labelledby="consent-title"
      className="mx-auto max-w-2xl rounded-2xl border border-line bg-surface p-7 sm:p-10"
    >
      <TGlyph size={44} />
      <h1 id="consent-title" className="mt-6 text-title font-semibold tracking-tight">
        Titan helps keep your number safe
      </h1>
      <p className="mt-4 text-lead text-ink-2">
        While you use this site, Titan notes how long each page takes and when you switch away. It never records
        what you type.
      </p>
      <ul className="mt-6 flex flex-col gap-2 text-body">
        <li>It helps us notice if someone is talking you through changes.</li>
        <li>It is used only to protect your account.</li>
        <li>You can change this any time in Security.</li>
      </ul>
      <div className="mt-8 flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={() => onChoose(true)}
          className="h-14 rounded-full bg-ink px-8 text-lead font-semibold text-surface transition-[transform,opacity] hover:opacity-90 active:scale-[0.98]"
        >
          That’s fine
        </button>
        <button
          type="button"
          onClick={() => onChoose(false)}
          className="h-14 rounded-full border border-line-strong bg-surface px-8 text-lead font-semibold transition-colors hover:bg-surface-2"
        >
          No thanks
        </button>
      </div>
    </section>
  );
}
