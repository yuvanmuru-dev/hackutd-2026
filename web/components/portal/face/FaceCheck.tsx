"use client";

// The face check (a few seconds, one blink) that runs after Maya taps "I'm doing this on my own" (D-007). It proves the person is Maya;
// it does not prove nobody is coaching her, so Titan keeps watching the call either way.
// If the check can't run at all (camera blocked, library or models fail) it returns null and the portal carries on
// as today. Once the camera and models are up, no face or no blink is a FAILED check, not a skipped one: otherwise
// "cover your camera" would get past it (the brain re-pauses on a failed result, D-007).
import { useEffect, useRef, useState } from "react";
import { FaceCamera } from "@/components/portal/face/FaceCamera";
import { closeCamera, loadHuman, openCamera, scan, verify } from "@/lib/face/engine";
import type { Contract as C } from "@/lib/api/client";

const SCAN_MS = 6000; // at most; ends about 1 s after a blink
const START_TIMEOUT_MS = 15000;

/** The check ran but saw no usable face or blink: report it as failed so the brain asks again. */
const NO_FACE: C.FaceResult = { match: false, similarity: 0, liveness: 0, antispoof: 0 };

export function FaceCheck({ onDone }: { onDone: (face: C.FaceResult | null) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [progress, setProgress] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [blinked, setBlinked] = useState(false);
  const done = useRef(onDone);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let over = false;
    let ready = false; // camera open and models loaded: from here on, "no result" means the check failed
    const el = video.current;
    const finish = (f: C.FaceResult | null) => {
      if (over) return;
      over = true;
      closeCamera(stream, el);
      done.current(f);
    };
    const timeout = setTimeout(() => finish(ready ? NO_FACE : null), START_TIMEOUT_MS + SCAN_MS);
    (async () => {
      if (!el) return finish(null);
      const [s] = await Promise.all([openCamera(el, () => over), loadHuman()]);
      stream = s;
      if (over) return closeCamera(s, el);
      ready = true;
      setScanning(true);
      const r = await scan(el, SCAN_MS, setProgress, { blink: true, onBlink: () => setBlinked(true) });
      finish(r ? await verify(r) : NO_FACE);
    })().catch(() => finish(ready ? NO_FACE : null));
    return () => {
      clearTimeout(timeout);
      over = true;
      closeCamera(stream, el);
    };
  }, []);

  return (
    <div className="mt-8">
      <p className="text-body font-semibold">Quick face check</p>
      <p className="mt-1 text-[16px] leading-6 text-ink-2">Look at the camera and blink slowly once. This stays on your device.</p>
      <div className="mt-4">
        <FaceCamera video={video} progress={progress} label={!scanning ? "Starting the camera…" : blinked ? "Got it. One moment…" : "Look at the camera and blink slowly once."} />
      </div>
    </div>
  );
}
