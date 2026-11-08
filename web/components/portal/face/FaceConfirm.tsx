"use client";

// After a passing face check: one last "are you sure?" before the protection goes off (D-007).
// The face check proves it's Maya, not that nobody is talking her through it, so the safe choice is the primary one.
import { useEffect, useRef } from "react";
import { BTN_PRIMARY, BTN_SECONDARY, NOTE } from "@/components/ui";
import { PROTECTION_COPY } from "@/components/portal/ProtectionToggle";
import type { ProtectionName } from "@/lib/api/client";

type Props = { name: ProtectionName; busy: boolean; onCancel: () => void; onContinue: () => void };

export function FaceConfirm({ name, busy, onCancel, onContinue }: Props) {
  const label = PROTECTION_COPY[name].name;
  const heading = useRef<HTMLParagraphElement>(null);
  useEffect(() => heading.current?.focus(), []);
  return (
    <div className="mt-8">
      <p ref={heading} tabIndex={-1} className={`${NOTE} border-positive font-semibold outline-none`}>
        Face check passed. It’s you.
      </p>
      <p className="mt-4 text-body font-semibold">Turn off {label}?</p>
      <p className="mt-1 text-[16px] leading-6 text-ink-2">
        {name === "port_out_protection"
          ? "Anyone with your account details could then move your number to another carrier."
          : PROTECTION_COPY[name].what}{" "}
        If someone on this call asked you to do this, cancel. Titan keeps watching the call either way.
      </p>
      <div className="mt-6 flex flex-col gap-3">
        <button type="button" onClick={onCancel} disabled={busy} className={`${BTN_PRIMARY} h-14 w-full text-lead`}>
          Cancel, keep it on
        </button>
        <button type="button" onClick={onContinue} disabled={busy} className={`${BTN_SECONDARY} h-14 w-full`}>
          {busy ? "One moment…" : `Continue and turn off ${label}`}
        </button>
      </div>
    </div>
  );
}
