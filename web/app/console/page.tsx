"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Wordmark } from "@/components/TGlyph";
import { BTN_DANGER, BTN_SECONDARY, NOTE, PANEL } from "@/components/ui";
import {
  demoPlay,
  demoReset,
  getCases,
  getTimeline,
  postEvent,
  type Contract as C,
  type DemoScenario,
} from "@/lib/api/client";
import { callEnded, callStarted, newDeviceLogin } from "@/lib/fixtures/events";

/** The show, in order (docs/DEMO.md). The next beat to run is the one filled button on the page. */
const BEATS: { id: DemoScenario; n: number; name: string; what: string }[] = [
  { id: "t2", n: 1, name: "T2 · Coached call", what: "Fake “T-Mobile Support” call: protection off, Transfer PIN" },
  { id: "t5", n: 2, name: "T5 · The callback", what: "The number reported in T2 calls back: “we can recover your money”" },
  { id: "t3", n: 3, name: "T3 · Scam text", what: "Maya forwards a lookalike-link text" },
];
const OTHER: { id: DemoScenario; name: string; what: string }[] = [
  { id: "t1", name: "T1 · Takeover", what: "New-device login, then a SIM swap" },
];

const finished = (c: C.Case) => c.status === "watching" || c.status === "closed";

/** Which beats have run, from the cases the brain holds: T5 shows up as a second coached case. */
function beatsDone(cases: C.Case[]): Record<DemoScenario, boolean> {
  const coached = cases.filter((c) => c.threat === "coached");
  return {
    t2: coached.some(finished),
    t5: coached.length >= 2,
    t3: cases.some((c) => c.threat === "scam_text"),
    t1: cases.some((c) => c.threat === "takeover"),
  };
}

// Backstage only. /demo/play returns before its events land, so refresh twice after a play.
export default function ConsolePage() {
  const [cases, setCases] = useState<C.Case[] | null>(null);
  const [timeline, setTimeline] = useState<C.Timeline | null>(null);
  const [down, setDown] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const timers = useRef<number[]>([]);

  const refresh = useCallback(() => {
    Promise.all([getCases(), getTimeline()])
      .then(([c, t]) => {
        setCases([...c].sort((a, b) => b.updated_at.localeCompare(a.updated_at)));
        setTimeline(t);
        setDown(false);
      })
      .catch(() => setDown(true));
  }, []);

  useEffect(() => {
    refresh();
    const t = timers.current;
    return () => t.forEach((id) => window.clearTimeout(id));
  }, [refresh]);

  const note = (line: string) =>
    setLog((l) => [`${new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", second: "2-digit" })} · ${line}`, ...l].slice(0, 8));

  async function run(label: string, fn: () => Promise<string>, later = false) {
    setBusy(label);
    try {
      note(await fn());
      refresh();
      if (later) timers.current.push(window.setTimeout(refresh, 1500), window.setTimeout(refresh, 4000));
    } catch {
      note(`${label} failed: is the brain running on :8000?`);
      setDown(true);
    } finally {
      setBusy(null);
    }
  }

  const active = timeline?.active_call ?? null;
  const done = beatsDone(cases ?? []);
  const running = (cases ?? []).some((c) => !finished(c));
  // T5 is the number reported in T2 calling back: it only makes sense after a finished T2 (and a T2 played
  // after T5 without a reset gets stuck in the brain), so it waits.
  const blocked = (id: DemoScenario) => (id === "t5" && !done.t2 ? "Run T2 first" : null);
  const next = running ? null : (BEATS.find((b) => !done[b.id] && !blocked(b.id))?.id ?? null);
  const play = (id: DemoScenario, name: string) => run(name, async () => (await demoPlay(id), `${name} started`), true);

  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-10 text-[16px] sm:px-8">
      <div className="flex flex-wrap items-center gap-4">
        <Wordmark size={30} />
        <h1 className="text-[24px] font-semibold">Demo console</h1>
        <button
          type="button"
          onClick={refresh}
          className={`ml-auto ${BTN_SECONDARY} !h-11 !px-4 !text-[15px]`}
        >
          Refresh
        </button>
      </div>
      {down && (
        <p role="alert" className={`${NOTE} mt-6 border-notice`}>
          Can’t reach the brain. Start it with: bash scripts/dev.sh
        </p>
      )}

      <section aria-labelledby="beats-title" className={`${PANEL} mt-8 p-5`}>
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <h2 id="beats-title" className="text-[20px] font-semibold">
            Demo beats
          </h2>
          <p className="text-[15px] text-ink-2" aria-live="polite">
            {running ? "A case is running. Wait for it to finish." : next ? `Next: ${BEATS.find((b) => b.id === next)?.name}` : "All three beats have run. Reset for another take."}
          </p>
        </div>
        <ol className="mt-4 grid gap-3 md:grid-cols-3">
          {BEATS.map((b) => {
            const why = blocked(b.id);
            const isNext = b.id === next;
            return (
              <li key={b.id} className="min-w-0">
                <button
                  type="button"
                  disabled={busy !== null || !!why}
                  aria-describedby={`beat-${b.id}-state`}
                  onClick={() => play(b.id, b.name)}
                  className={`flex h-full min-h-[120px] w-full flex-col items-start gap-2 rounded-control border px-5 py-4 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                    isNext
                      ? "border-accent bg-accent text-accent-ink hover:bg-accent-hover"
                      : "border-line-strong bg-surface text-ink hover:bg-surface-2"
                  }`}
                >
                  <span className="flex w-full items-baseline gap-3">
                    <span className="text-[28px] font-bold leading-none tabular">{b.n}</span>
                    <span className="text-[20px] font-semibold leading-tight">{b.name}</span>
                  </span>
                  <span className={`text-[15px] leading-snug ${isNext ? "text-accent-ink" : "text-ink-2"}`}>{b.what}</span>
                  <span id={`beat-${b.id}-state`} className={`mt-auto text-[14px] font-semibold ${isNext ? "text-accent-ink" : "text-ink-3"}`}>
                    {why ?? (done[b.id] ? "Played · play again" : isNext ? "Play next" : "Not played yet")}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start">
        <section aria-labelledby="play-title" className={`${PANEL} p-5`}>
          <h2 id="play-title" className="text-[18px] font-semibold">
            Other scenarios
          </h2>
          <ul className="mt-4 flex flex-col gap-3">
            {OTHER.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => play(s.id, s.name)}
                  className="flex min-h-12 w-full items-center justify-between gap-4 rounded-control border border-line-strong bg-surface px-4 py-3 text-left transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <span className="flex flex-col">
                    <span className="text-[16px] font-semibold text-ink">{s.name}</span>
                    <span className="text-[14px] text-ink-3">{s.what}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>

          <h2 className="mt-8 text-[18px] font-semibold">Single events</h2>
          <div className="mt-4 flex flex-wrap gap-3">
            <EventButton
              label="Call starts (unverified “T-Mobile Support”)"
              disabled={busy !== null || !!active}
              onClick={() =>
                run("Call starts", async () => {
                  const r = await postEvent(callStarted());
                  return `Call started${r.case_id ? ` · case ${r.case_id}` : ""}`;
                })
              }
            />
            <EventButton
              label="Call ends"
              disabled={busy !== null || !active}
              onClick={() =>
                run("Call ends", async () => {
                  if (!active) return "No active call";
                  await postEvent(callEnded(active.call_id, active.started_at));
                  return "Call ended";
                })
              }
            />
            <EventButton
              label="Login from a new device (Lagos)"
              disabled={busy !== null}
              onClick={() =>
                run("New-device login", async () => {
                  await postEvent(newDeviceLogin());
                  return "New-device login sent";
                })
              }
            />
          </div>
          <p className="mt-4 text-meta text-ink-2" aria-live="polite">
            {active ? `Call active: ${active.caller_name ?? "unknown"} (${active.attestation})` : "No call active"}
          </p>

          <div className="mt-8 border-t border-line pt-5">
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => {
                if (!window.confirm("Reset demo data? This deletes every case and event.")) return;
                run("Reset", async () => (await demoReset(), "Reset: all cases and events cleared"));
              }}
              className={`${BTN_DANGER} w-full`}
            >
              Reset demo data
            </button>
            <p className="mt-2 text-[14px] text-ink-3">Deletes every case and event.</p>
          </div>
        </section>

        <section aria-labelledby="cases-title" className={`${PANEL} p-5`}>
          <h2 id="cases-title" className="text-[18px] font-semibold">
            Cases {cases ? <span className="text-ink-2 tabular">· {cases.length}</span> : null}
          </h2>
          <ul className="mt-4 divide-y divide-line" aria-live="polite">
            {cases?.length === 0 && <li className="py-3 text-ink-2">No cases yet. Play a scenario.</li>}
            {cases?.map((c) => (
              <li key={c.case_id} className="flex flex-wrap items-center gap-x-4 gap-y-3 py-4">
                <div className="min-w-0 basis-full sm:basis-0 sm:flex-1">
                  <p className="font-semibold">{c.title}</p>
                  <p className="text-meta text-ink-2 tabular">
                    {c.case_number} · {c.status}
                    {c.threat ? ` · ${c.threat} (${c.confidence})` : ""}
                  </p>
                </div>
                <Link
                  href={`/guardian/${encodeURIComponent(c.case_id)}`}
                  className={`${BTN_SECONDARY} !h-11 !px-4 !text-[15px]`}
                >
                  Guardian
                </Link>
                <Link
                  href={`/case/${encodeURIComponent(c.case_id)}`}
                  className={`${BTN_SECONDARY} !h-11 !px-4 !text-[15px]`}
                >
                  Customer view
                </Link>
              </li>
            ))}
          </ul>

          <h2 className="mt-8 text-[18px] font-semibold">Recent</h2>
          <ul className="mt-3 flex flex-col gap-1 text-meta text-ink-2 tabular">
            {log.length === 0 && <li>Nothing yet</li>}
            {log.map((l, i) => (
              <li key={`${i}-${l}`}>{l}</li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  );
}

function EventButton({ label, disabled, onClick }: { label: string; disabled: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`${BTN_SECONDARY} !h-auto min-h-11 !px-4 py-2 !text-[15px]`}
    >
      {label}
    </button>
  );
}
