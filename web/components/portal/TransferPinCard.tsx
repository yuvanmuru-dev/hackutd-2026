"use client";

import { useState } from "react";
import type { Contract as C } from "@/lib/api/client";
import { notePinPaste } from "@/lib/behavior/session";

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
    ? `Your PIN will be ready in 24 hours.${holdUntil ? ` It unlocks ${fmtWhen(holdUntil)}.` : ""}`
    : pin.status === "active"
      ? "Your transfer PIN is active."
      : "";

  return (
    <div>
      {/* Always mounted, so the result of "Generate" is announced when its text changes. */}
      <p role="status" className="sr-only">
        {announce}
      </p>
      {isHeld ? (
        <div className="rounded-xl bg-notice-soft p-5">
          <p className="text-lead font-semibold text-notice">Your PIN will be ready in 24 hours.</p>
          <p className="mt-1">
            New transfer PINs wait 24 hours when they’re requested during a call we can’t verify.
            {holdUntil ? ` It unlocks ${fmtWhen(holdUntil)}.` : ""}
          </p>
        </div>
      ) : pin.status === "active" ? (
        <div className="rounded-xl bg-positive-soft p-5">
          <p className="text-lead font-semibold text-positive">Your transfer PIN is active.</p>
        </div>
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (ready) onRequest();
          }}
        >
          <label className="flex flex-col gap-2">
            <span className="font-semibold">Account PIN</span>
            <input
              type="password"
              name="account_pin"
              inputMode="numeric"
              autoComplete="off"
              maxLength={8}
              size={8}
              value={value}
              onChange={(e) => setValue(e.target.value.replace(/\D/g, ""))}
              onPaste={() => notePinPaste()}
              className="h-14 w-full min-w-0 rounded-xl border border-control bg-surface px-4 text-lead tracking-[0.3em] tabular"
              aria-describedby="tpin-help"
            />
            <span id="tpin-help" className="text-meta text-ink-2">
              4 to 8 digits. It stays on this page.
            </span>
          </label>
          <button
            type="submit"
            disabled={!ready || busy || disabled}
            className="h-14 w-full rounded-full bg-ink px-8 text-lead font-semibold text-surface transition-[transform,opacity] hover:opacity-90 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto sm:self-start"
          >
            {busy ? "Requesting…" : "Generate transfer PIN"}
          </button>
        </form>
      )}
    </div>
  );
}
