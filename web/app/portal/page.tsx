"use client";

import { useRouter } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { ConsentScreen } from "@/components/portal/ConsentScreen";
import { PortalShell } from "@/components/portal/PortalShell";
import { ProtectAside, SPLIT } from "@/components/portal/ProtectAside";
import { BTN_PRIMARY, PANEL } from "@/components/ui";
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
        <div className={SPLIT}>
          <ConsentScreen
            onChoose={(yes) => {
              setConsent(yes);
              setChosen(yes);
              if (yes) resetFlow("/portal");
            }}
          />
          <ProtectAside />
        </div>
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
        data: {
          device_hash: "h_maya_laptop",
          region: "Dallas, TX",
          new_device: false,
          succeeded: true,
        },
      });
    } catch {
      /* the account page shows the connection problem */
    }
    router.push("/portal/security");
  }

  return (
    <PortalShell>
      <div className={SPLIT}>
        <section className={`w-full max-w-[440px] ${PANEL} p-6 sm:p-8`}>
          <h1 className="text-title font-bold tracking-[-0.01em]">Sign in</h1>
          <p className="mt-2 text-body text-ink-2">
            This device is saved to your account.
          </p>
          <div className="mt-6 flex items-center gap-4 border-y border-line py-4">
            <span
              aria-hidden
              className="grid h-12 w-12 place-items-center rounded-full bg-surface-2 text-[20px] font-semibold text-ink"
            >
              M
            </span>
            <div>
              <p className="text-body font-semibold">Maya</p>
              <p className="text-[15px] text-ink-3 tabular">
                <span aria-hidden>(214) •••-••48</span>
                <span className="sr-only">Phone number ending in 48</span> · Primary Account Holder
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={signIn}
            disabled={busy}
            className={`${BTN_PRIMARY} mt-6 !h-14 w-full !text-lead`}
          >
            {busy ? "Signing in…" : "Continue"}
          </button>
          <p className="mt-4 text-[15px] text-ink-3">
            Not you? Sign in with a different T-Mobile ID
          </p>
        </section>
        <ProtectAside />
      </div>
    </PortalShell>
  );
}
