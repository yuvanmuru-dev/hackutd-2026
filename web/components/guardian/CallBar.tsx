"use client";

import { useEffect, useState } from "react";
import type { Contract as C } from "@/lib/api/client";
import { formatDuration, isRiskyMarker, markerLabel } from "./derive";

const ATTESTATION: Record<C.CallSummary["attestation"], string> = {
  A: "verified number",
  B: "partly verified",
  C: "unverified number",
  none: "no caller verification",
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
        <span className="text-[22px] font-semibold">No phone call in this case</span>
        <span className="g-label">Titan is working from account activity only.</span>
      </section>
    );
  }

  const start = Date.parse(call.started_at);
  const span = Math.max(1, seconds * 1000);
  const ongoing = !call.ended_at;
  const pos = (ts: string) => Math.min(100, Math.max(0, ((Date.parse(ts) - start) / span) * 100));
  const visible = markers.filter((m) => m.type !== "call.started" && m.type !== "call.ended");

  return (
    <section className="g-panel grid grid-cols-[auto_1fr] items-center gap-x-10 px-6 py-5" aria-label="Call">
      <div>
        <p className="g-label">{ongoing ? "On the phone for" : "Call lasted"}</p>
        <p className="text-[56px] font-bold leading-none tracking-tight tabular" aria-live="off">
          {formatDuration(seconds)}
        </p>
      </div>
      <div className="min-w-0">
        <p className="text-[22px] font-semibold leading-snug">
          “{call.caller_name ?? "Unknown caller"}”
          <span className="font-normal text-[var(--g-ink-2)]">
            {" "}
            · {ATTESTATION[call.attestation]}
            {call.seen_before ? "" : " · never called her before"}
            {call.scam_label ? " · reported as scam" : ""}
          </span>
        </p>
        <div className="mt-5">
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
            {visible.length === 0 && <li className="text-[var(--g-ink-3)]">No account changes during the call yet</li>}
            {visible.map((m) => (
              <li key={m.event_id} className="whitespace-nowrap">
                <span className="tabular text-[var(--g-ink-3)]">
                  {formatDuration((Date.parse(m.ts) - start) / 1000)}
                </span>{" "}
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
