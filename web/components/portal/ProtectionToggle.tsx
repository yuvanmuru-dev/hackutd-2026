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
  name: ProtectionName;
  enabled: boolean;
  busy: boolean;
  disabled: boolean;
  onChange: (next: boolean) => void;
};

export function ProtectionToggle({ name, enabled, busy, disabled, onChange }: Props) {
  const copy = PROTECTION_COPY[name];
  const id = `prot-${name}`;
  return (
    <li className="flex items-center gap-5 py-5">
      <div className="min-w-0 flex-1">
        <p id={id} className="text-lead font-semibold">
          {copy.name}
        </p>
        <p className="text-ink-2">{copy.what}</p>
      </div>
      <span className={`hidden w-12 text-right font-semibold sm:inline ${enabled ? "text-positive" : "text-ink-3"}`}>
        {busy ? "…" : enabled ? "On" : "Off"}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        aria-labelledby={id}
        disabled={disabled || busy}
        onClick={() => onChange(!enabled)}
        className={`relative h-10 w-[72px] flex-none rounded-full transition-colors duration-200 disabled:opacity-50 ${
          enabled ? "bg-positive" : "bg-line-strong"
        }`}
      >
        <span
          aria-hidden
          className={`absolute top-1 left-1 h-8 w-8 rounded-full bg-surface shadow-[0_1px_3px_rgb(0_0_0/0.25)] transition-transform duration-200 ${
            enabled ? "translate-x-8" : ""
          }`}
        />
      </button>
    </li>
  );
}
