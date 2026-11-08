"use client";

// The camera view both face screens share: a mirrored 4:3 preview with a thin magenta progress rule.
// Frames never leave the browser; only the numbers from engine.ts do.
import type { RefObject } from "react";

export function FaceCamera({ video, progress, label }: { video: RefObject<HTMLVideoElement | null>; progress: number; label: string }) {
  return (
    <figure className="overflow-hidden rounded-panel border border-line bg-surface-2">
      <div className="relative aspect-[4/3] w-full">
        <video
          ref={video}
          muted
          playsInline
          aria-label="Camera preview, stays on this device"
          className="absolute inset-0 h-full w-full -scale-x-100 object-cover"
        />
        <div aria-hidden className="pointer-events-none absolute inset-[18%_26%] rounded-[50%] border-2 border-surface/80" />
      </div>
      <div className="h-1 bg-line" aria-hidden>
        <div className="h-full bg-accent transition-[width] duration-100 ease-linear" style={{ width: `${Math.round(progress * 100)}%` }} />
      </div>
      <figcaption role="status" className="px-4 py-3 text-[16px] leading-6 text-ink-2">
        {label}
      </figcaption>
    </figure>
  );
}
