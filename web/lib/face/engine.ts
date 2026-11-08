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
    iris: { enabled: false },
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

export type Scan = { embedding: number[]; score: number; liveness: number; antispoof: number };

/**
 * Watch the video for `ms` and keep the strongest face. Liveness and anti-spoof take their best frame,
 * so one blink or a bad frame doesn't fail Maya. Returns null if no face was seen.
 */
export async function scan(video: HTMLVideoElement, ms: number, onTick?: (frac: number) => void): Promise<Scan | null> {
  const human = await loadHuman();
  const start = performance.now();
  let best: Scan | null = null;
  let liveness = 0;
  let antispoof = 0;
  while (performance.now() - start < ms) {
    const r = await human.detect(video);
    const f = r.face[0];
    if (f && f.embedding && f.embedding.length > 0) {
      liveness = Math.max(liveness, f.live ?? 0);
      antispoof = Math.max(antispoof, f.real ?? 0);
      if (!best || f.score > best.score) best = { embedding: Array.from(f.embedding), score: f.score, liveness: 0, antispoof: 0 };
    }
    onTick?.(Math.min(1, (performance.now() - start) / ms));
    await new Promise((res) => setTimeout(res, 60));
  }
  return best && { ...best, liveness, antispoof };
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
  return { match: sim >= MIN_SIMILARITY, similarity: round(sim), liveness: round(s.liveness), antispoof: round(s.antispoof) };
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
