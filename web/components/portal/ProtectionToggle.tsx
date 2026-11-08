"use client";

import type { ProtectionName } from "@/lib/api/client";

export const PROTECTION_COPY: Record<ProtectionName, { name: string; what: string }> = {
  sim_protection: {
    name: "SIM Protection",
    what: "Blocks anyone from moving your number to a new SIM card.",
  },
  port_out_protection: {
    name: "Port Out Protection",
    what: "Stops your number from being moved to another carrier.",
  },
  scam_block: {
    name: "Scam Block",
    what: "Stops calls from numbers reported as scams.",
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

/** One switch row. The word On/Off always shows, so state never rests on the track colour. */
export function SwitchRow({ id, name, what, enabled, busy, disabled, onChange }: Props) {
  return (
    <li className="flex items-center gap-4 py-5 first:pt-1 last:pb-1">
      <div className="min-w-0 flex-1">
        <p id={id} className="text-lead font-semibold leading-snug">
          {name}
        </p>
        <p className="mt-1 text-ink-2">{what}</p>
      </div>
      <span className={`w-10 flex-none text-right font-semibold ${enabled ? "text-positive" : "text-ink-2"}`} aria-hidden>
        {busy ? "…" : enabled ? "On" : "Off"}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        aria-labelledby={id}
        aria-busy={busy || undefined}
        disabled={disabled || busy}
        onClick={() => onChange(!enabled)}
        className={`relative h-10 w-[68px] flex-none rounded-full transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-50 ${
          enabled ? "bg-positive" : "bg-control"
        }`}
      >
        <span
          aria-hidden
          className={`absolute top-1 left-1 h-8 w-8 rounded-full bg-surface shadow-[0_1px_3px_rgb(0_0_0/0.3)] transition-transform duration-200 ${
            enabled ? "translate-x-7" : ""
          }`}
        />
      </button>
    </li>
  );
}

export function ProtectionToggle(props: Omit<Props, "id" | "name" | "what"> & { name: ProtectionName }) {
  const copy = PROTECTION_COPY[props.name];
  return <SwitchRow {...props} id={`prot-${props.name}`} name={copy.name} what={copy.what} />;
}
