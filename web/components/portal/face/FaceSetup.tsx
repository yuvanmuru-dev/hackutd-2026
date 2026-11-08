"use client";

// "Set up face check" on Privacy and security (D-007). Optional and off by default. The face descriptor is
// stored only in this browser; nothing is sent to Titan or T-Mobile when you set it up.
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { BTN_PRIMARY, BTN_SECONDARY } from "@/components/ui";
import { FaceCamera } from "@/components/portal/face/FaceCamera";
import { clearEnrollment, closeCamera, enrolled, loadHuman, openCamera, saveEnrollment, scan, subscribeEnrollment } from "@/lib/face/engine";

type Step = "idle" | "starting" | "scanning" | "error";

export function FaceSetup() {
  const isEnrolled = useSyncExternalStore(subscribeEnrollment, enrolled, () => false);
  const [step, setStep] = useState<Step>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const cancelled = useRef(false);

  useEffect(() => () => closeCamera(stream.current, video.current), []);

  function stop() {
    cancelled.current = true;
    closeCamera(stream.current, video.current);
    stream.current = null;
  }

  async function start() {
    cancelled.current = false;
    setError(null);
    setProgress(0);
    setStep("starting");
    try {
      // The <video> mounts with the "starting" step; wait for the ref.
      for (let i = 0; i < 20 && !video.current; i++) await new Promise((r) => setTimeout(r, 25));
      if (!video.current) throw new Error("no video");
      const [s] = await Promise.all([openCamera(video.current, () => cancelled.current), loadHuman()]);
      stream.current = s;
      setStep("scanning");
      const result = await scan(video.current, 2500, setProgress);
      if (cancelled.current) return;
      stop();
      if (!result || result.score < 0.5) {
        setError("We couldn’t see your face clearly. Face the camera in good light and try again.");
        setStep("error");
        return;
      }
      saveEnrollment(result.embedding);
      setStep("idle");
    } catch {
      stop();
      setError("Face check isn’t available on this device or the camera is blocked. Nothing has changed.");
      setStep("error");
    }
  }

  const active = step === "starting" || step === "scanning";

  return (
    <div className="py-4">
      <div className="flex flex-wrap items-center gap-4">
        <div className="min-w-0 flex-1">
          <p id="face-title" className="text-body font-semibold leading-6">
            Face check
          </p>
          <p id="face-what" className="mt-0.5 text-[16px] leading-6 text-ink-2">
            {isEnrolled
              ? "On for this device. We’ll check it’s you before a protection is turned off during a call."
              : "Check it’s you before a protection is turned off during a call."}
          </p>
        </div>
        {isEnrolled && !active ? (
          <button type="button" onClick={clearEnrollment} aria-describedby="face-what" className={`${BTN_SECONDARY} h-11 flex-none`}>
            Remove
          </button>
        ) : active ? (
          <button type="button" onClick={() => (stop(), setStep("idle"))} className={`${BTN_SECONDARY} h-11 flex-none`}>
            Cancel
          </button>
        ) : (
          <button type="button" onClick={start} aria-describedby="face-what" className={`${BTN_PRIMARY} h-11 flex-none`}>
            Set up face check
          </button>
        )}
      </div>

      {active && (
        <div className="mt-4 max-w-[420px]">
          <FaceCamera
            video={video}
            progress={progress}
            label={step === "starting" ? "Starting the camera…" : "Look at the camera and hold still."}
          />
        </div>
      )}
      <div role="status">
        {step === "error" && error && <p className="mt-3 border-l-4 border-notice py-1 pl-3 text-[16px] leading-6">{error}</p>}
      </div>
      <p className="mt-3 text-[15px] leading-6 text-ink-3">
        Your face stays on this device. Titan gets only a yes or no and three scores, never a photo.
      </p>
    </div>
  );
}
