"use client";

import { useState } from "react";
import type { Contract as C } from "@/lib/api/client";
import { notePinPaste } from "@/lib/behavior/session";
import { BTN_DARK, LABEL, NOTE } from "@/components/ui";

type Props = {
  pin: C.ProtectionState["transfer_pin"];
  held: { until: string | null } | null;
  busy: boolean;
  disabled: boolean;
  onRequest: () => void;
};

const fmtWhen = (iso: string) =>
  new Intl.DateTimeFormat("en-US", { weekday: "long", hour: "numeric", minute: "2-digit" }).format(new Date(iso));

// The account PIN never leaves this field: nothing reads its value. Only a paste into it is noted (D-006).
export function TransferPinPanel({ pin, held, busy, disabled, onRequest }: Props) {
  const [value, setValue] = useState("");
  const holdUntil = held?.until ?? (pin.status === "held" ? pin.hold_until : null);
  const isHeld = pin.status === "held" || !!held;
  const ready = value.length >= 4;
  const announce = isHeld
    ? `Your Transfer PIN will be ready in 24 hours.${holdUntil ? ` It unlocks ${fmtWhen(holdUntil)}.` : ""}`
    : pin.status === "active"
      ? "Your Transfer PIN is active."
      : pin.status === "revoked"
        ? "Your last Transfer PIN was cancelled. You can request a new one."
        : "";

  return (
    <div>
      {/* Always mounted, so the result of "Generate" is announced when its text changes. */}
      <p role="status" className="sr-only">
        {announce}
      </p>
      {isHeld ? (
        <div className={`${NOTE} my-4 border-notice`}>
          <p className="font-semibold">Your Transfer PIN will be ready in 24 hours.</p>
          <p className="mt-1 text-ink-2">
            Transfer PINs requested during a call we can’t verify are held for 24 hours.
            {holdUntil ? ` It unlocks ${fmtWhen(holdUntil)}.` : ""}
          </p>
        </div>
      ) : pin.status === "active" ? (
        <p className="flex items-center gap-3 py-4 font-semibold">
          <svg aria-hidden width="20" height="20" viewBox="0 0 20 20" fill="none" className="flex-none text-positive">
            <path d="M4 10.5l4 4 8-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Your Transfer PIN is active.
        </p>
      ) : (
        <>
          {pin.status === "revoked" && (
            <div className={`${NOTE} mt-4 border-ink`}>
              <p className="font-semibold">Your last Transfer PIN was cancelled.</p>
              <p className="mt-1 text-ink-2">
                You asked Titan to cancel it after that call, so it can’t be used. You can request a new one.
              </p>
            </div>
          )}
        <form
          className="flex flex-col gap-4 py-5"
          onSubmit={(e) => {
            e.preventDefault();
            if (!ready) return;
            setValue(""); // the account PIN doesn't stay in the field once it's been used
            onRequest();
          }}
        >
          <div className="flex flex-col gap-2">
            <label htmlFor="tpin-input" className={LABEL}>
              Account PIN
            </label>
            <input
              id="tpin-input"
              type="password"
              name="account_pin"
              inputMode="numeric"
              autoComplete="off"
              maxLength={8}
              size={8}
              value={value}
              onChange={(e) => setValue(e.target.value.replace(/\D/g, ""))}
              onPaste={() => notePinPaste()}
              className="h-12 w-full max-w-[240px] min-w-0 rounded-control border border-control bg-surface px-4 text-lead tracking-[0.3em]"
              aria-describedby="tpin-help"
            />
            <span id="tpin-help" className="text-[15px] text-ink-3">
              4 to 8 digits. Your PIN stays on this page.
            </span>
          </div>
          <button
            type="submit"
            disabled={!ready || busy || disabled}
            className={`${BTN_DARK} w-full sm:w-auto sm:self-start`}
          >
            {busy ? "Requesting…" : "Request Transfer PIN"}
          </button>
        </form>
        </>
      )}
    </div>
  );
}
