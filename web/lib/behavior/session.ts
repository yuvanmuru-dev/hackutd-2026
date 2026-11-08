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
  /** Gaps between keydowns in one field burst, in ms. Timing only: no key values, no field contents (D-006). */
  keyIntervals?: number[];
  /** A pause screen or hold was shown in this flow: don't learn the baseline from it. */
  paused?: boolean;
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
  keyIntervals: [],
  paused: false,
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

// ---- Typing rhythm (D-006). Only keydown timestamps are used, turned into gaps here; the key pressed and
// what was typed are never read. Her baseline stays on this device (localStorage) and never leaves it.
// Only the single distance number is sent, inside portal_signals.
const BASELINE = "titan.rhythm.baseline";
const DEMO_BASELINE: Rhythm = { median: 180, cv: 0.35 }; // plausible seed for Maya when this browser has none
const MIN_INTERVALS = 3; // a 4-digit PIN gives 3 gaps: enough for the demo PIN to count
const MAX_INTERVALS = 200;
type Rhythm = { median: number; cv: number };

/** One gap between two keydowns in the same field (the hook drops gaps over 2 s as pauses). */
export function noteKeyInterval(ms: number) {
  if (!Number.isFinite(ms) || ms <= 0 || ms > 2000) return;
  update((s) => {
    const k = (s.keyIntervals ??= []);
    k.push(Math.round(ms));
    if (k.length > MAX_INTERVALS) k.splice(0, k.length - MAX_INTERVALS);
  });
}

/** A pause screen or hold appeared: this flow won't update her baseline. */
export function notePaused() {
  update((s) => {
    s.paused = true;
  });
}

function features(xs: number[] | undefined): Rhythm | null {
  if (!xs || xs.length < MIN_INTERVALS) return null;
  const sorted = [...xs].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  const median = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
  const sd = Math.sqrt(xs.reduce((a, b) => a + (b - mean) ** 2, 0) / xs.length);
  return { median: Math.max(median, 1), cv: mean > 0 ? sd / mean : 0 };
}

function baseline(): Rhythm {
  try {
    const b = JSON.parse(localStorage.getItem(BASELINE) ?? "null") as Rhythm | null;
    if (b && b.median > 0 && Number.isFinite(b.cv)) return b;
  } catch {
    /* fall through to the seed */
  }
  return DEMO_BASELINE;
}

/** 0 = her usual rhythm; about 1 per "clearly different" step. Null with too little typing to judge. */
function rhythmDistance(xs: number[] | undefined): number | null {
  const f = features(xs);
  if (!f) return null;
  const b = baseline();
  const d = Math.abs(Math.log(f.median / b.median)) / 0.4 + Math.abs(f.cv - b.cv) / 0.25;
  return Math.round(Math.min(10, Math.max(0, d)) * 100) / 100;
}

/** End of a normal flow (no pause screen): nudge her on-device baseline toward this session. */
function learnBaseline(s: State) {
  if (s.paused) return;
  const f = features(s.keyIntervals);
  if (!f) return;
  const b = baseline();
  const a = 0.2; // slow moving average
  try {
    localStorage.setItem(BASELINE, JSON.stringify({ median: b.median + a * (f.median - b.median), cv: b.cv + a * (f.cv - b.cv) }));
  } catch {
    /* ignore */
  }
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
    typing_rhythm_distance: rhythmDistance(s.keyIntervals),
  };
}

/** Starts a new flow on the same session; the current page stays as the first step. */
export function resetFlow(currentPath?: string, endedNormally = false) {
  const prev = read();
  if (endedNormally) learnBaseline(prev);
  const s = fresh(prev.session_id);
  if (currentPath) s.steps.push({ path: currentPath, startedAt: now(), ms: null });
  write(s);
}
