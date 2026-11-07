"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { CallingScreen, PauseScreen } from "@/components/portal/PauseScreen";
import { PortalShell } from "@/components/portal/PortalShell";
import { ProtectionToggle } from "@/components/portal/ProtectionToggle";
import { TransferPinCard } from "@/components/portal/TransferPinCard";
import {
  BrainError,
  check,
  getProtections,
  MAYA,
  newEventId,
  nowIso,
  postEvent,
  requestTransferPin,
  setProtection,
  type Contract as C,
  type ProtectionName,
} from "@/lib/api/client";
import { consentGiven, resetFlow, snapshot } from "@/lib/behavior/session";
import { useBehavior } from "@/lib/behavior/useBehavior";

const ORDER: ProtectionName[] = ["sim_protection", "port_out_protection", "scam_block"];
const subscribe = () => () => {};

type Overlay =
  | { kind: "pause"; name: ProtectionName; screen: NonNullable<C.CheckResponse["pause_screen"]>; reasons: string[] }
  | { kind: "calling"; caseId: string | null }
  | null;

export default function SecurityPage() {
  const consent = useSyncExternalStore(subscribe, consentGiven, () => null) === true;
  useBehavior("/portal/security", consent);

  const [state, setState] = useState<C.ProtectionState | null>(null);
  const [down, setDown] = useState(false);
  const [busy, setBusy] = useState<ProtectionName | "pin" | null>(null);
  const [overlay, setOverlay] = useState<Overlay>(null);
  const [choiceBusy, setChoiceBusy] = useState<"help" | "continue" | null>(null);
  const [held, setHeld] = useState<{ until: string | null } | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    getProtections()
      .then((s) => {
        setState(s);
        setDown(false);
      })
      .catch(() => setDown(true));
  }, []);
  useEffect(load, [load]);

  const signals = () => (consent ? { portal_signals: snapshot() } : {});

  /** End of a flow: send the behavior summary once, then start a fresh flow. */
  const finishFlow = useCallback(() => {
    if (!consent) return;
    const data = snapshot();
    resetFlow("/portal/security");
    postEvent({ event_id: newEventId(), user_id: MAYA, type: "portal.signals", ts: nowIso(), source: "portal", call_id: null, data }).catch(
      () => {},
    );
  }, [consent]);

  async function apply(name: ProtectionName, checkId: string) {
    try {
      setState(await setProtection(name, { enabled: false, via: "portal", check_id: checkId }));
      setOverlay(null);
      finishFlow();
    } catch (e) {
      if (e instanceof BrainError && e.status === 409) return turnOff(name); // skipped the pause: ask again
      setNotice("That didn’t go through. Please try again.");
      setOverlay(null);
    }
  }

  async function turnOff(name: ProtectionName) {
    setBusy(name);
    setNotice(null);
    try {
      const r = await check({ user_id: MAYA, action: "protection_off", protection: name, ...signals() });
      if (r.decision === "allow") await apply(name, r.check_id);
      else if (r.decision === "pause" && r.pause_screen)
        setOverlay({ kind: "pause", name, screen: r.pause_screen, reasons: r.reasons });
      else if (r.decision === "block") setOverlay({ kind: "calling", caseId: r.case_id ?? null });
      else setNotice(r.reasons[0] ?? "We can’t make that change right now.");
    } catch {
      setDown(true);
    } finally {
      setBusy(null);
    }
  }

  async function turnOn(name: ProtectionName) {
    setBusy(name);
    try {
      setState(await setProtection(name, { enabled: true, via: "portal" }));
    } catch {
      setNotice("That didn’t go through. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  async function choose(choice: "on_call_help" | "doing_it_myself") {
    if (overlay?.kind !== "pause") return;
    const name = overlay.name;
    setChoiceBusy(choice === "on_call_help" ? "help" : "continue");
    try {
      const r = await check({ user_id: MAYA, action: "protection_off", protection: name, customer_choice: choice, ...signals() });
      if (choice === "on_call_help") {
        setOverlay({ kind: "calling", caseId: r.case_id ?? null });
        finishFlow();
        load();
      } else if (r.decision === "allow") {
        await apply(name, r.check_id);
      } else if (r.decision === "pause" && r.pause_screen) {
        setOverlay({ kind: "pause", name, screen: r.pause_screen, reasons: r.reasons });
      } else {
        setOverlay(null);
        setNotice(r.reasons[0] ?? "We can’t make that change right now.");
      }
    } catch {
      setOverlay(null);
      setDown(true);
    } finally {
      setChoiceBusy(null);
    }
  }

  async function transferPin() {
    setBusy("pin");
    try {
      const r = await requestTransferPin();
      setState(r.protections);
      if (r.check.decision === "hold") setHeld({ until: r.check.hold_until ?? null });
      finishFlow();
    } catch {
      setDown(true);
    } finally {
      setBusy(null);
    }
  }

  return (
    <PortalShell signedIn>
      <h1 className="text-title font-semibold tracking-tight">Security</h1>
      <p className="mt-2 text-lead text-ink-2">Protections that keep your phone number yours.</p>

      {down && (
        <p role="alert" className="mt-6 rounded-xl bg-notice-soft p-5 text-body font-semibold text-notice">
          Can’t reach Titan right now. Your protections stay as they are.{" "}
          <button type="button" onClick={load} className="underline underline-offset-4">
            Try again
          </button>
        </p>
      )}
      {notice && (
        <p role="status" className="mt-6 rounded-xl bg-surface-2 p-5 text-body">
          {notice}
        </p>
      )}
      {state?.shield_mode && (
        <p role="status" className="mt-6 rounded-xl bg-accent-soft p-5 text-body">
          <span className="font-semibold">Extra checks are on during this call.</span> Changes to protections ask you
          one question first.
        </p>
      )}

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <section aria-labelledby="prot-title" className="rounded-2xl border border-line bg-surface px-6 py-4 sm:px-8">
          <h2 id="prot-title" className="pt-3 text-[26px] font-semibold tracking-tight">
            Number protections
          </h2>
          <ul className="divide-y divide-line">
            {ORDER.map((name) => {
              const p = state?.protections.find((x) => x.name === name);
              return (
                <ProtectionToggle
                  key={name}
                  name={name}
                  enabled={p?.enabled ?? false}
                  busy={busy === name}
                  disabled={!state || busy !== null}
                  onChange={(next) => (next ? turnOn(name) : turnOff(name))}
                />
              );
            })}
          </ul>
        </section>
        {state && (
          <TransferPinCard
            pin={state.transfer_pin}
            held={held}
            busy={busy === "pin"}
            disabled={busy !== null}
            onRequest={transferPin}
          />
        )}
      </div>

      {overlay?.kind === "pause" && (
        <PauseScreen
          screen={overlay.screen}
          reasons={overlay.reasons}
          busy={choiceBusy}
          onHelp={() => choose("on_call_help")}
          onContinue={() => choose("doing_it_myself")}
        />
      )}
      {overlay?.kind === "calling" && <CallingScreen caseId={overlay.caseId} onClose={() => setOverlay(null)} />}
    </PortalShell>
  );
}
