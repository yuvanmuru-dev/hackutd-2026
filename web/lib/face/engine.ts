// Optional on-device face check (D-007). Runs @vladmandic/human (MIT) in the browser. The face descriptor lives
// only in this browser's localStorage; the brain receives only {match, similarity, liveness, antispoof}.
import type { Config, Human } from "@vladmandic/human";
import type { Contract as C } from "@/lib/api/client";

/** All face UI is hidden unless NEXT_PUBLIC_FACE_CHECK=1 (default off, so the demo path is unchanged). */
export const FACE_CHECK = process.env.NEXT_PUBLIC_FACE_CHECK === "1";

const KEY = "titan.face.v1";
const CHANGE = "titan-face-change";
/** Same-person threshold for human's descriptor similarity (0..1). */
export const MIN_SIMILARITY = 0.5;

const CONFIG: Partial<Config> = {
  // Served from /public by scripts/copy-face-models.mjs, so no request leaves for a CDN either.
  modelBasePath: process.env.NEXT_PUBLIC_FACE_MODELS ?? "/face-models/",
  backend: "webgl",
  debug: false,
  cacheSensitivity: 0,
  filter: { enabled: true, equalization: false },
  face: {
    enabled: true,
    detector: { rotation: false, maxDetected: 1, return: false },
    mesh: { enabled: true },
    iris: { enabled: true }, // sharpens the eyelid points the blink check reads
    description: { enabled: true },
    emotion: { enabled: false },
    antispoof: { enabled: true },
    liveness: { enabled: true },
  },
  body: { enabled: false },
  hand: { enabled: false },
  object: { enabled: false },
  gesture: { enabled: false },
  segmentation: { enabled: false },
} as Partial<Config>;

// human.detect() merges a per-call config into its own, so both passes set all three explicitly.
const pass = (on: boolean) =>
  ({ face: { description: { enabled: on }, antispoof: { enabled: on }, liveness: { enabled: on } } }) as Partial<Config>;
const HEAVY = pass(true);
const LIGHT = pass(false);

let loading: Promise<Human> | null = null;

/** Load once; later calls reuse it. Rejects if the library or models can't load (callers fall back silently). */
export function loadHuman(): Promise<Human> {
  loading ??= (async () => {
    // Aliased to the browser ESM build in next.config.ts (the package root resolves to tfjs-node on the server).
    const mod = await import("@vladmandic/human");
    const H = mod.Human ?? mod.default;
    const human = new H(CONFIG);
    await human.load();
    await human.warmup();
    return human;
  })().catch((e) => {
    loading = null;
    throw e;
  });
  return loading;
}

export type Scan = { embedding: number[]; score: number; liveness: number; antispoof: number; blinked: boolean };
type Mesh = number[][];

/** Eyelid gap over eye height, both eyes averaged (same mesh points as human's own "blink" gesture). */
function eyeOpen(m: Mesh): number | null {
  if (!m || m.length < 468) return null;
  const r = (a: number, b: number, c: number, d: number) => Math.abs(m[a][1] - m[b][1]) / Math.max(1e-6, Math.abs(m[c][1] - m[d][1]));
  return (r(374, 386, 443, 450) + r(145, 159, 223, 230)) / 2;
}

/**
 * Watch the video and keep the strongest face. With `blink`, also watch for one blink: the eyelid gap drops
 * below 55% of this person's own open-eye level and comes back above 80%. A photo can't blink on request,
 * which the bundled anti-spoof model alone couldn't tell apart on a laptop camera (live 0.78 vs photo 0.77).
 * Without `blink` it runs for `ms`; with it, until a blink plus 1 s of frames, or `ms` at most.
 */
export async function scan(
  video: HTMLVideoElement,
  ms: number,
  onTick?: (frac: number) => void,
  opts: { blink?: boolean; onBlink?: () => void } = {},
): Promise<Scan | null> {
  const human = await loadHuman();
  const start = performance.now();
  let best: Omit<Scan, "liveness" | "antispoof" | "blinked"> | null = null;
  let liveness = 0;
  let antispoof = 0;
  let openMax = 0;
  let closed = false;
  let blinked = false;
  let frames = 0;
  let openMin = Infinity;
  let lastHeavy = -Infinity;
  while (performance.now() - start < ms) {
    // The blink check needs many frames a second, so the heavy models (face ID, liveness, anti-spoof) run about
    // once every 700 ms (every 250 ms once she has blinked) and the light ones (detector, mesh, iris) run on every frame.
    const heavy = !opts.blink || !best || performance.now() - lastHeavy > (blinked ? 250 : 700);
    const r = await human.detect(video, heavy ? HEAVY : LIGHT);
    if (heavy) lastHeavy = performance.now();
    const f = r.face[0];
    if (f && heavy && f.embedding && f.embedding.length > 0) {
      liveness = Math.max(liveness, f.live ?? 0);
      antispoof = Math.max(antispoof, f.real ?? 0);
      if (!best || f.score > best.score) best = { embedding: Array.from(f.embedding), score: f.score };
    }
    if (f) {
      const open = opts.blink ? eyeOpen(f.mesh as Mesh) : null;
      frames++;
      if (open !== null) openMin = Math.min(openMin, open);
      if (open !== null && !blinked) {
        openMax = Math.max(openMax, open);
        if (openMax > 0 && open < openMax * 0.55) closed = true;
        else if (closed && open > openMax * 0.8) {
          blinked = true;
          opts.onBlink?.();
        }
      }
    }
    const elapsed = performance.now() - start;
    onTick?.(Math.min(1, elapsed / ms));
    // After the blink, keep sampling until liveness clears the brain's 0.8 bar too (or time runs out).
    if (opts.blink && blinked && elapsed > 1000 && best && liveness >= 0.8) break;
    await new Promise((res) => setTimeout(res, opts.blink ? 10 : 60));
  }
  onTick?.(1);
  if (opts.blink) console.debug("[face] blink check", { frames, ms: Math.round(performance.now() - start), openMax, openMin, blinked });
  return best && { ...best, liveness, antispoof, blinked };
}

export async function similarity(a: number[], b: number[]): Promise<number> {
  const human = await loadHuman();
  return human.match.similarity(a, b);
}

// ---- enrollment, this browser only
type Enrollment = { embedding: number[]; created_at: string };

function read(): Enrollment | null {
  if (typeof window === "undefined") return null;
  try {
    const v = JSON.parse(window.localStorage.getItem(KEY) ?? "null");
    return v && Array.isArray(v.embedding) ? v : null;
  } catch {
    return null;
  }
}

export const enrolled = (): boolean => read() !== null;

export function subscribeEnrollment(cb: () => void): () => void {
  window.addEventListener(CHANGE, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(CHANGE, cb);
    window.removeEventListener("storage", cb);
  };
}

export function saveEnrollment(embedding: number[]) {
  window.localStorage.setItem(KEY, JSON.stringify({ embedding, created_at: new Date().toISOString() }));
  window.dispatchEvent(new Event(CHANGE));
}

export function clearEnrollment() {
  window.localStorage.removeItem(KEY);
  window.dispatchEvent(new Event(CHANGE));
}

/** The contract's FaceResult: four numbers, nothing else leaves the device. */
export async function verify(s: Scan): Promise<C.FaceResult | null> {
  const e = read();
  if (!e) return null;
  const sim = Math.max(0, Math.min(1, await similarity(e.embedding, s.embedding)));
  const round = (n: number) => Math.round(Math.max(0, Math.min(1, n)) * 100) / 100;
  // antispoof: 1 when she blinked on request; otherwise the model's score, capped at 0.5 so a still image
  // (which can't blink) never clears the brain's 0.8 bar.
  const antispoof = s.blinked ? 1 : Math.min(s.antispoof, 0.5);
  return { match: sim >= MIN_SIMILARITY, similarity: round(sim), liveness: round(s.liveness), antispoof: round(antispoof) };
}

// ---- camera
/** `cancelled` is checked once the camera opens, so a check that was abandoned never takes over the <video>. */
export async function openCamera(video: HTMLVideoElement, cancelled: () => boolean = () => false): Promise<MediaStream> {
  const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: 640, height: 480 }, audio: false });
  if (cancelled()) {
    stream.getTracks().forEach((t) => t.stop());
    throw new Error("cancelled");
  }
  video.srcObject = stream;
  await video.play();
  return stream;
}

export function closeCamera(stream: MediaStream | null, video: HTMLVideoElement | null) {
  stream?.getTracks().forEach((t) => t.stop());
  if (video && stream && video.srcObject === stream) video.srcObject = null;
}
