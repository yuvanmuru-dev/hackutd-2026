"use client";

import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { ConsentScreen } from "@/components/portal/ConsentScreen";
import { PortalShell } from "@/components/portal/PortalShell";
import { MAYA, newEventId, nowIso, postEvent } from "@/lib/api/client";
import { consentGiven, resetFlow, setConsent } from "@/lib/behavior/session";
import { useBehavior } from "@/lib/behavior/useBehavior";

// No real auth (D-014): one demo customer, Maya, on her usual laptop.
const subscribe = () => () => {};

export default function PortalSignIn() {
  const router = useRouter();
  const stored = useSyncExternalStore(subscribe, consentGiven, () => null);
  const [chosen, setChosen] = useState<boolean | null>(null);
  const consent = chosen ?? stored;
  const [busy, setBusy] = useState(false);
  useBehavior("/portal", consent === true);

  if (consent === null) {
    return (
      <PortalShell>
        <ConsentScreen
          onChoose={(yes) => {
            setConsent(yes);
            setChosen(yes);
            if (yes) resetFlow("/portal");
          }}
        />
      </PortalShell>
    );
  }

  async function signIn() {
    setBusy(true);
    try {
      await postEvent({
        event_id: newEventId(),
        user_id: MAYA,
        type: "login",
        ts: nowIso(),
        source: "portal",
        call_id: null,
        data: { device_hash: "h_maya_laptop", region: "Dallas, TX", new_device: false, succeeded: true },
      });
    } catch {
      /* the account page shows the connection problem */
    }
    router.push("/portal/security");
  }

  return (
    <PortalShell>
      <section className="mx-auto max-w-xl rounded-2xl border border-line bg-surface p-7 sm:p-10">
        <h1 className="text-title font-semibold tracking-tight">Sign in</h1>
        <p className="mt-3 text-lead text-ink-2">Welcome back. This laptop is saved to your account.</p>
        <div className="mt-8 flex items-center gap-4 rounded-xl bg-surface-2 p-5">
          <span className="grid h-14 w-14 place-items-center rounded-full bg-accent-soft text-[24px] font-bold text-accent">
            M
          </span>
          <div>
            <p className="text-lead font-semibold">Maya</p>
            <p className="text-ink-2 tabular">(214) •••-••48</p>
          </div>
        </div>
        <button
          type="button"
          onClick={signIn}
          disabled={busy}
          className="mt-8 h-14 w-full rounded-full bg-ink text-lead font-semibold text-surface transition-transform active:scale-[0.98] disabled:opacity-60"
        >
          {busy ? "Signing in…" : "Continue as Maya"}
        </button>
      </section>
    </PortalShell>
  );
}
