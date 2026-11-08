"use client";

import { useCallback, useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { CallingScreen, PauseScreen } from "@/components/portal/PauseScreen";
import { NOTE, PANEL } from "@/components/ui";
import { PortalShell } from "@/components/portal/PortalShell";
import { ProtectionToggle, SwitchRow } from "@/components/portal/ProtectionToggle";
import { TransferPinPanel } from "@/components/portal/TransferPinCard";
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
import { consentGiven, notePaused, resetFlow, setConsent, snapshot } from "@/lib/behavior/session";
import { useBehavior } from "@/lib/behavior/useBehavior";
import { FaceCheck } from "@/components/portal/face/FaceCheck";
import { FaceConfirm } from "@/components/portal/face/FaceConfirm";
import { FaceSetup } from "@/components/portal/face/FaceSetup";
import { enrolled, FACE_CHECK, loadHuman } from "@/lib/face/engine";

const ORDER: ProtectionName[] = ["sim_protection", "port_out_protection", "scam_block"];
const subscribe = () => () => {};

type Overlay =
  | { kind: "pause"; name: ProtectionName; screen: NonNullable<C.CheckResponse["pause_screen"]>; reasons: string[]; face?: "check" | { checkId: string } }
  | { kind: "calling"; caseId: string | null }
  | null;

/**
 * Settings in two columns (design-taste app sheet: achromatic ledger): a label column with the
 * section's title and help beside a borderless panel. Stacks on a phone. Sizes stay at Maya's 18px floor.
 */
function Section({ id, title, help, children }: { id: string; title: string; help: ReactNode; children: ReactNode }) {
  return (
    <section
      aria-labelledby={id}
      className="grid grid-cols-1 gap-4 border-t border-line py-8 first:border-t-0 first:pt-0 md:grid-cols-[minmax(0,340px)_minmax(0,1fr)] md:gap-12"
    >
      <div>
        <h2 id={id} className="text-[20px] font-semibold leading-7">
          {title}
        </h2>
        <div className="mt-1.5 text-[16px] leading-6 text-ink-2">{help}</div>
      </div>
      <div className={`min-w-0 self-start ${PANEL} px-5 sm:px-6`}>{children}</div>
    </section>
  );
}

export default function SecurityPage() {
  const stored = useSyncExternalStore(subscribe, consentGiven, () => null);
  const [consentChoice, setConsentChoice] = useState<boolean | null>(null);
  const consent = (consentChoice ?? stored) === true;
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
        // The brain is the source of truth: once it no longer holds the PIN (hold over, demo reset), drop ours.
        if (s.transfer_pin.status !== "held") setHeld(null);
      })
      .catch(() => setDown(true));
  }, []);
  useEffect(load, [load]);

  // Titan changes her protections on its own (it turns Port Out Protection back on right after a held
  // Transfer PIN), and the console can reset everything: keep the page in step with the brain. Skipped
  // while she is mid-change or a dialog is open, so a refresh never fights her own click.
  const idle = busy === null && overlay === null && choiceBusy === null;
  useEffect(() => {
    if (!idle) return;
    const id = setInterval(() => {
      if (document.visibilityState === "visible") load();
    }, 2000);
    return () => clearInterval(id);
  }, [idle, load]);

  const signals = () => (consent ? { portal_signals: snapshot() } : {});

  /** End of a flow: send the behavior summary once, then start a fresh flow. */
  const finishFlow = useCallback(() => {
    if (!consent) return;
    const data = snapshot();
    resetFlow("/portal/security", true); // learns her typing baseline only if no pause screen or hold was shown
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
      setNotice("That change didn’t go through. Your protection is still on. Please try again.");
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
      else setNotice(r.reasons[0] ?? "We can’t make that change right now. Your protection is still on.");
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
      setNotice("That change didn’t go through. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  // Optional face check (D-007): only when the flag is on and this browser has a face set up. Undefined = not run yet.
  const faceOn = () => FACE_CHECK && enrolled();
  useEffect(() => {
    if (overlay?.kind === "pause" && faceOn()) loadHuman().catch(() => {}); // warm the models while she reads
  }, [overlay?.kind]);

  async function choose(choice: "on_call_help" | "doing_it_myself", face?: C.FaceResult | null) {
    if (overlay?.kind !== "pause") return;
    const name = overlay.name;
    if (choice === "doing_it_myself" && face === undefined && faceOn()) {
      setOverlay({ ...overlay, face: "check" });
      return;
    }
    if (overlay.face) setOverlay({ ...overlay, face: undefined });
    setChoiceBusy(choice === "on_call_help" ? "help" : "continue");
    try {
      const r = await check({
        user_id: MAYA,
        action: "protection_off",
        protection: name,
        customer_choice: choice,
        ...signals(),
        ...(face ? { face } : {}),
      });
      if (choice === "on_call_help") {
        setOverlay({ kind: "calling", caseId: r.case_id ?? null });
        finishFlow();
        load();
      } else if (r.decision === "allow" && face) {
        // Face check passed: one last "are you sure?" before anything changes.
        setOverlay({ ...overlay, face: { checkId: r.check_id } });
      } else if (r.decision === "allow") {
        await apply(name, r.check_id);
      } else if (r.decision === "pause" && r.pause_screen) {
        setOverlay({ kind: "pause", name, screen: r.pause_screen, reasons: r.reasons });
      } else {
        setOverlay(null);
        setNotice(r.reasons[0] ?? "We can’t make that change right now. Your protection is still on.");
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
      if (r.check.decision === "hold") {
        notePaused();
        setHeld({ until: r.check.hold_until ?? null });
      }
      finishFlow();
    } catch {
      setDown(true);
    } finally {
      setBusy(null);
    }
  }

  // A pause screen in this flow: don’t learn her typing baseline from it.
  useEffect(() => {
    if (consent && overlay?.kind === "pause") notePaused();
  }, [consent, overlay?.kind]);

  const shield = !!state?.shield_mode;

  return (
    <PortalShell signedIn current="Security">
      <h1 className="text-title font-bold tracking-[-0.01em]">Privacy and security</h1>
      <p className="mt-2 text-body text-ink-2">Manage the protections on your account and lines.</p>

      {/* Always mounted so screen readers announce changes; empty when there is nothing to say. */}
      <div role="status">
        {down && (
          <p className={`${NOTE} mt-6 border-notice`}>
            We can’t reach your account right now. Nothing has changed.{" "}
            <button type="button" onClick={load} className="underline underline-offset-4 hover:no-underline">
              Try again
            </button>
          </p>
        )}
        {notice && <p className={`${NOTE} mt-6 border-ink`}>{notice}</p>}
        {shield && (
          <p className={`${NOTE} mt-6 border-accent`}>
            <span className="font-semibold">Extra checks are on while you’re on a call.</span> We’ll ask one question
            before a protection is turned off.
          </p>
        )}
      </div>

      <div className="mt-8">
        <Section
          id="prot-title"
          title="Protections"
          help={<p>Free features that stop bad actors from moving your number to another device or carrier, and that block likely scam calls.</p>}
        >
          {state ? (
            <>
              <p className="flex flex-wrap items-center justify-between gap-x-4 border-b border-line py-3 text-[15px] text-ink-3">
                <span>
                  Maya · <span aria-hidden>(214) •••-••48</span>
                  <span className="sr-only">phone number ending in 48</span>
                </span>
                <span>Primary Account Holder</span>
              </p>
              <ul>
              {ORDER.map((name) => {
                const p = state.protections.find((x) => x.name === name);
                return (
                  <ProtectionToggle
                    key={name}
                    name={name}
                    enabled={p?.enabled ?? false}
                    busy={busy === name}
                    disabled={busy !== null}
                    onChange={(next) => (next ? turnOn(name) : turnOff(name))}
                  />
                );
              })}
              </ul>
            </>
          ) : (
            <p className="py-4 text-ink-2">
              {down ? "Not available right now. Your protections are unchanged." : "Loading…"}
            </p>
          )}
        </Section>

        <Section
          id="tpin-title"
          title="Transfer PIN"
          help={<p>You need a Transfer PIN only when you move your number to another carrier. T-Mobile will never call and ask for it.</p>}
        >
          {state ? (
            <TransferPinPanel
              pin={state.transfer_pin}
              held={held}
              busy={busy === "pin"}
              disabled={busy !== null}
              onRequest={transferPin}
            />
          ) : (
            <p className="py-4 text-ink-2">{down ? "Not available right now." : "Loading…"}</p>
          )}
        </Section>

        {FACE_CHECK && (
          <Section
            id="face-section-title"
            title="Face check"
            help={<p>Optional. Face ID checks who you are; Titan still watches whether someone is talking you through it.</p>}
          >
            <FaceSetup />
          </Section>
        )}

        <Section
          id="notes-title"
          title="Coaching detection"
          help={<p>Timing only, such as how long a page takes. Never what you type.</p>}
        >
          <ul>
            <SwitchRow
              id="notes-switch"
              name="Let Titan notice coaching"
              what="Helps Titan spot when someone is talking you through changes."
              enabled={consent}
              busy={false}
              disabled={false}
              onChange={(next) => {
                setConsent(next);
                setConsentChoice(next);
                if (next) resetFlow("/portal/security");
              }}
            />
          </ul>
        </Section>
      </div>

      {overlay?.kind === "pause" && (
        <PauseScreen
          screen={overlay.screen}
          reasons={overlay.reasons}
          busy={choiceBusy}
          onHelp={() => choose("on_call_help")}
          onContinue={() => choose("doing_it_myself")}
          faceCheck={
            overlay.face === "check" ? (
              <FaceCheck onDone={(f) => choose("doing_it_myself", f)} />
            ) : overlay.face ? (
              <FaceConfirm
                name={overlay.name}
                busy={choiceBusy !== null}
                onCancel={() => {
                  setOverlay(null);
                  finishFlow();
                }}
                onContinue={async () => {
                  if (overlay.kind !== "pause" || typeof overlay.face !== "object") return;
                  setChoiceBusy("continue");
                  try {
                    await apply(overlay.name, overlay.face.checkId);
                  } finally {
                    setChoiceBusy(null);
                  }
                }}
              />
            ) : undefined
          }
        />
      )}
      {overlay?.kind === "calling" && <CallingScreen caseId={overlay.caseId} onClose={() => setOverlay(null)} />}
    </PortalShell>
  );
}
