"use client";

import { Wordmark } from "@/components/TGlyph";
import { BTN_DARK, BTN_SECONDARY, PANEL } from "@/components/ui";

// First visit only. Plain words about what the behavior summary is and isn't.
export function ConsentScreen({ onChoose }: { onChoose: (yes: boolean) => void }) {
  return (
    <section aria-labelledby="consent-title" className={`w-full max-w-[560px] ${PANEL} p-6 sm:p-8`}>
      <Wordmark size={24} />
      <h1 id="consent-title" className="mt-6 text-title font-bold">
        Help Titan notice coaching
      </h1>
      <p className="mt-3 text-body text-ink-2">
        Titan can note how long each page takes and when you switch away. It never records what you type, and it
        only uses this to protect your account.
      </p>
      <ul className="mt-5 divide-y divide-line border-y border-line text-body [&>li]:py-3">
        <li>Helps spot when someone is talking you through changes</li>
        <li>Used only to protect your account</li>
        <li>You can change this any time under Privacy and security</li>
      </ul>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <button type="button" onClick={() => onChoose(true)} className={`${BTN_DARK} w-full sm:w-auto`}>
          Allow
        </button>
        <button type="button" onClick={() => onChoose(false)} className={`${BTN_SECONDARY} w-full sm:w-auto`}>
          Not now
        </button>
      </div>
    </section>
  );
}
