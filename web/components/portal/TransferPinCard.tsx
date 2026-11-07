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
  new Date(iso).toLocaleString("en-US", { weekday: "long", hour: "numeric", minute: "2-digit" });

// The account PIN never leaves this field: nothing reads its value. Only a paste into it is noted (D-006).
export function TransferPinCard({ pin, held, busy, disabled, onRequest }: Props) {
  const [value, setValue] = useState("");
  const holdUntil = held?.until ?? (pin.status === "held" ? pin.hold_until : null);
  const ready = value.length >= 4;

  return (
    <section aria-labelledby="tpin-title" className="rounded-2xl border border-line bg-surface p-6 sm:p-8">
      <h2 id="tpin-title" className="text-[26px] font-semibold tracking-tight">
        Transfer PIN
      </h2>
      <p className="mt-2 text-ink-2">You only need this when you move your number to a new carrier.</p>

      {pin.status === "held" || held ? (
        <div className="mt-6 rounded-xl bg-notice-soft p-5" role="status">
          <p className="text-lead font-semibold text-notice">Your PIN will be ready in 24 hours.</p>
          <p className="mt-1 text-body">
            We hold new transfer PINs during calls we can’t verify.
            {holdUntil ? ` It unlocks ${fmtWhen(holdUntil)}.` : ""}
          </p>
        </div>
      ) : pin.status === "active" ? (
        <div className="mt-6 rounded-xl bg-positive-soft p-5" role="status">
          <p className="text-lead font-semibold text-positive">Your transfer PIN is active.</p>
        </div>
      ) : (
        <form
          className="mt-6 flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (ready) onRequest();
          }}
        >
          <label className="flex flex-1 flex-col gap-2">
            <span className="font-semibold">Account PIN</span>
            <input
              type="password"
              inputMode="numeric"
              autoComplete="off"
              maxLength={8}
              value={value}
              onChange={(e) => setValue(e.target.value.replace(/\D/g, ""))}
              onPaste={() => notePinPaste()}
              className="h-14 rounded-xl border border-line-strong bg-surface px-4 text-lead tracking-[0.3em] tabular"
              aria-describedby="tpin-help"
            />
            <span id="tpin-help" className="text-meta text-ink-2">
              4 to 8 digits. It stays on this page.
            </span>
          </label>
          <button
            type="submit"
            disabled={!ready || busy || disabled}
            className="h-14 rounded-full bg-ink px-8 text-lead font-semibold text-surface transition-transform active:scale-[0.98] disabled:opacity-50"
          >
            {busy ? "Requesting…" : "Generate transfer PIN"}
          </button>
        </form>
      )}
    </section>
  );
}
