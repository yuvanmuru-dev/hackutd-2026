"use client";

import { useEffect, useState } from "react";
import type { Contract as C } from "@/lib/api/client";
import { formatDuration, isRiskyMarker, markerLabel } from "./derive";

const ATTESTATION: Record<C.CallSummary["attestation"], string> = {
  A: "Verified caller ID",
  B: "Partly verified caller ID",
  C: "Unverified caller ID",
  none: "No caller verification",
};

/** Live call clock: ticks only while the call is still open and we are live. */
function useCallSeconds(call: C.CallSummary | null, live: boolean) {
  const [now, setNow] = useState<number | null>(null);
  const open = !!call && !call.ended_at && live;
  useEffect(() => {
    if (!open) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [open]);
  if (!call) return 0;
  if (open && now) return Math.max(call.duration_s, (now - Date.parse(call.started_at)) / 1000);
  return call.duration_s;
}

export function CallBar({ call, markers, live }: { call: C.CallSummary | null; markers: C.Event[]; live: boolean }) {
  const seconds = useCallSeconds(call, live);

  if (!call) {
    return (
      <section className="g-panel flex items-center gap-6 px-6 py-4" aria-label="Call">
        <span className="text-[20px] font-semibold">No phone call in this case</span>
        <span className="g-label">Titan is working from account activity only.</span>
      </section>
    );
  }

  const start = Date.parse(call.started_at);
  const span = Math.max(1, seconds * 1000);
  const ongoing = !call.ended_at;
  const pos = (ts: string) => Math.min(100, Math.max(0, ((Date.parse(ts) - start) / span) * 100));
  const visible = markers.filter((m) => m.type !== "call.started" && m.type !== "call.ended");
  const risky = visible.filter((m) => isRiskyMarker(m));

  return (
    <section className="g-panel grid grid-cols-1 items-center gap-x-10 gap-y-4 px-5 py-4 sm:grid-cols-[auto_1fr] sm:px-6" aria-label="Call">
      <div>
        <p className="g-label">{ongoing ? "Call time" : "Call lasted"}</p>
        <p className="mt-1 text-[32px] font-semibold leading-none tabular" aria-live="off">
          {formatDuration(seconds)}
        </p>
      </div>
      <div className="min-w-0">
        <p className="text-[20px] font-semibold leading-snug">
          “{call.caller_name ?? "Unknown caller"}”
          <span className="font-normal text-[var(--g-ink-2)]">
            {" "}
            · {ATTESTATION[call.attestation]}
            {call.seen_before ? "" : " · first call from this number"}
            {call.scam_label ? " · reported as scam" : ""}
          </span>
        </p>
        <div className="mt-4">
          <div className="g-track">
            <div className="g-track-fill" style={{ width: "100%" }} />
            {visible.map((m) => (
              <span
                key={m.event_id}
                className="g-marker"
                data-risky={isRiskyMarker(m)}
                style={{ left: `${pos(m.ts)}%` }}
                title={markerLabel(m)}
              />
            ))}
          </div>
          <ol className="mt-4 flex flex-wrap gap-x-7 gap-y-1 text-[17px]" aria-label="During this call">
            {risky.length === 0 && <li className="text-[var(--g-ink-3)]">No risky changes during the call yet</li>}
            {risky.map((m) => (
              <li key={m.event_id} className="whitespace-nowrap">
                <span className="tabular text-[var(--g-ink-3)]">
                  {formatDuration((Date.parse(m.ts) - start) / 1000)}
                </span>{" "}
                {isRiskyMarker(m) && <span className="g-diamond" aria-hidden />}
                <span
                  className={isRiskyMarker(m) ? "font-semibold" : ""}
                  style={{ color: isRiskyMarker(m) ? "var(--g-accent)" : "var(--g-ink-2)" }}
                >
                  {markerLabel(m)}
                </span>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
