// Portal behavior summary (D-006): derived numbers only. Never keys, never typed text.
// State lives in sessionStorage so one flow can span /portal -> /portal/security.
import type { Contract as C } from "@/lib/api/client";

const KEY = "titan.behavior.v1";
const CONSENT = "titan.consent.v1";

type Step = { path: string; startedAt: number; ms: number | null };
type State = {
  session_id: string;
  steps: Step[];
  lastActivity: number;
  hesitation_ms: number;
  paste_into_pin: boolean;
  tab_switches: number;
  speedSum: number;
  speedCount: number;
};

const now = () => Date.now();
const fresh = (session_id: string): State => ({
  session_id,
  steps: [],
  lastActivity: now(),
  hesitation_ms: 0,
  paste_into_pin: false,
  tab_switches: 0,
  speedSum: 0,
  speedCount: 0,
});

function read(): State {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (raw) return JSON.parse(raw) as State;
  } catch {
    /* storage blocked: fall through to a fresh in-memory state */
  }
  const s = fresh(`ses_${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`);
  write(s);
  return s;
}

function write(s: State) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(s));
  } catch {
    /* ignore */
  }
}

function update(fn: (s: State) => void) {
  const s = read();
  fn(s);
  write(s);
}

export const getSessionId = () => read().session_id;

export function consentGiven(): boolean | null {
  try {
    const v = localStorage.getItem(CONSENT);
    return v === null ? null : v === "yes";
  } catch {
    return null;
  }
}

export function setConsent(v: boolean) {
  try {
    localStorage.setItem(CONSENT, v ? "yes" : "no");
  } catch {
    /* ignore */
  }
}

/** Records an interaction; the gap since the last one counts toward hesitation. */
export function noteActivity() {
  update((s) => {
    const t = now();
    s.hesitation_ms = Math.max(s.hesitation_ms, t - s.lastActivity);
    s.lastActivity = t;
  });
}

export function noteTabSwitch() {
  update((s) => {
    s.tab_switches += 1;
  });
}

export function notePinPaste() {
  update((s) => {
    s.paste_into_pin = true;
  });
}

export function notePointerSpeed(pxPerMs: number) {
  if (!Number.isFinite(pxPerMs) || pxPerMs <= 0 || pxPerMs > 20) return;
  update((s) => {
    s.speedSum += pxPerMs;
    s.speedCount += 1;
  });
}

export function markStep(path: string) {
  update((s) => {
    const last = s.steps.at(-1);
    if (last?.path === path && last.ms === null) return;
    const t = now();
    if (last && last.ms === null) last.ms = t - last.startedAt;
    s.steps.push({ path, startedAt: t, ms: null });
    s.lastActivity = t;
  });
}

/** Exactly the 8 PortalSignals keys (additionalProperties: false in the contract). */
export function snapshot(): C.PortalSignals {
  const s = read();
  const t = now();
  return {
    session_id: s.session_id,
    page_path: s.steps.map((x) => x.path),
    ms_per_step: s.steps.map((x) => Math.round(x.ms ?? t - x.startedAt)),
    hesitation_ms: Math.round(Math.max(s.hesitation_ms, t - s.lastActivity)),
    paste_into_pin: s.paste_into_pin,
    tab_switches: Math.round(s.tab_switches),
    pointer_speed: s.speedCount >= 10 ? Math.round((s.speedSum / s.speedCount) * 100) / 100 : null,
    typing_rhythm_distance: null,
  };
}

/** Starts a new flow on the same session; the current page stays as the first step. */
export function resetFlow(currentPath?: string) {
  const s = fresh(read().session_id);
  if (currentPath) s.steps.push({ path: currentPath, startedAt: now(), ms: null });
  write(s);
}
