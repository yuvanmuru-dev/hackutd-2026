"use client";

// The ~3 s face check that runs after Maya taps "I'm doing this on my own" (D-007). It proves the person is Maya;
// it does not prove nobody is coaching her, so Titan keeps watching the call either way.
// Any failure to run (camera blocked, library or models fail) returns null and the portal carries on as today.
import { useEffect, useRef, useState } from "react";
import { FaceCamera } from "@/components/portal/face/FaceCamera";
import { closeCamera, loadHuman, openCamera, scan, verify } from "@/lib/face/engine";
import type { Contract as C } from "@/lib/api/client";

const SCAN_MS = 3000;
const START_TIMEOUT_MS = 15000;

export function FaceCheck({ onDone }: { onDone: (face: C.FaceResult | null) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [progress, setProgress] = useState(0);
  const [scanning, setScanning] = useState(false);
  const done = useRef(onDone);

  useEffect(() => {
    let stream: MediaStream | null = null;
    let over = false;
    const el = video.current;
    const finish = (f: C.FaceResult | null) => {
      if (over) return;
      over = true;
      closeCamera(stream, el);
      done.current(f);
    };
    const timeout = setTimeout(() => finish(null), START_TIMEOUT_MS + SCAN_MS);
    (async () => {
      if (!el) return finish(null);
      const [s] = await Promise.all([openCamera(el, () => over), loadHuman()]);
      stream = s;
      if (over) return closeCamera(s, el);
      setScanning(true);
      const r = await scan(el, SCAN_MS, setProgress);
      finish(r ? await verify(r) : null);
    })().catch(() => finish(null));
    return () => {
      clearTimeout(timeout);
      over = true;
      closeCamera(stream, el);
    };
  }, []);

  return (
    <div className="mt-8">
      <p className="text-body font-semibold">Quick face check</p>
      <p className="mt-1 text-[16px] leading-6 text-ink-2">Checking it’s you. This stays on your device.</p>
      <div className="mt-4">
        <FaceCamera video={video} progress={progress} label={scanning ? "Look at the camera…" : "Starting the camera…"} />
      </div>
    </div>
  );
}
