"use client";

import { useEffect, useRef, useState } from "react";
import type { ProtectionName } from "@/lib/api/client";

export const PROTECTION_COPY: Record<ProtectionName, { name: string; what: string }> = {
  sim_protection: {
    name: "SIM Protection",
    what: "Prevents your number from being moved to another SIM or device.",
  },
  port_out_protection: {
    name: "Port Out Protection",
    what: "Blocks unauthorized transfers of your line to another wireless carrier.",
  },
  scam_block: {
    name: "Scam Block",
    what: "Blocks calls identified as likely scams before they reach you.",
  },
};

type Props = {
  id: string;
  name: string;
  what: string;
  enabled: boolean;
  busy: boolean;
  disabled: boolean;
  onChange: (next: boolean) => void;
};

/**
 * One switch row, T-Mobile style: name and one line of what it does, a small switch on the right.
 * The word On/Off stays (quiet, beside the switch) so state never rests on the track colour, and it turns
 * into "Saving…" / "Saved" around a change. Magenta on the track is the one colour on this page: "it's on".
 */
export function SwitchRow({ id, name, what, enabled, busy, disabled, onChange }: Props) {
  const [saved, setSaved] = useState(false);
  const wasBusy = useRef(busy);
  useEffect(() => {
    const finished = wasBusy.current && !busy;
    wasBusy.current = busy;
    if (!finished) return;
    const show = setTimeout(() => setSaved(true), 0);
    const hide = setTimeout(() => setSaved(false), 2000);
    return () => {
      clearTimeout(show);
      clearTimeout(hide);
    };
  }, [busy]);
  return (
    <li className="flex items-center gap-4 border-b border-line py-4 last:border-b-0">
      <div className="min-w-0 flex-1">
        <p id={id} className="text-body font-semibold leading-6">
          {name}
        </p>
        <p className="mt-0.5 text-[16px] leading-6 text-ink-2">{what}</p>
      </div>
      <span aria-live="polite" className="flex-none text-right text-[15px] text-ink-3">
        {busy ? "Saving…" : saved ? "Saved" : <span aria-hidden>{enabled ? "On" : "Off"}</span>}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        aria-labelledby={id}
        aria-busy={busy || undefined}
        disabled={disabled || busy}
        onClick={() => onChange(!enabled)}
        className="-mr-2 inline-flex h-11 w-14 flex-none items-center justify-center rounded-control disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span
          aria-hidden
          className={`relative h-5 w-9 rounded-full transition-colors duration-150 ${enabled ? "bg-accent" : "bg-control"}`}
        >
          <span
            className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-surface transition-transform duration-150 ${
              enabled ? "translate-x-4" : ""
            }`}
          />
        </span>
      </button>
    </li>
  );
}

export function ProtectionToggle(props: Omit<Props, "id" | "name" | "what"> & { name: ProtectionName }) {
  const copy = PROTECTION_COPY[props.name];
  return <SwitchRow {...props} id={`prot-${props.name}`} name={copy.name} what={copy.what} />;
}
