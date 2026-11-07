"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Wordmark } from "@/components/TGlyph";
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

const SCENARIOS: { id: DemoScenario; name: string; what: string }[] = [
  { id: "t2", name: "Play T2: coached call", what: "Fake support call, protection off, transfer PIN" },
  { id: "t1", name: "Play T1: takeover", what: "New-device login, then a SIM swap" },
  { id: "t3", name: "Play T3: scam text", what: "Maya forwards a lookalike-link text" },
];

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

  return (
    <main className="mx-auto w-full max-w-6xl px-5 py-10 sm:px-8">
      <div className="flex flex-wrap items-center gap-4">
        <Wordmark size={32} />
        <h1 className="text-title font-semibold tracking-tight">Demo console</h1>
        <button
          type="button"
          onClick={refresh}
          className="ml-auto h-11 rounded-full border border-line-strong bg-surface px-5 font-semibold transition-colors hover:bg-surface-2"
        >
          Refresh
        </button>
      </div>
      {down && (
        <p role="alert" className="mt-6 rounded-xl bg-notice-soft p-4 font-semibold text-notice">
          Can’t reach the brain. Start it with: bash scripts/dev.sh
        </p>
      )}

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section aria-labelledby="play-title" className="rounded-2xl border border-line bg-surface p-6">
          <h2 id="play-title" className="text-lead font-semibold">
            Scenarios
          </h2>
          <ul className="mt-4 flex flex-col gap-3">
            {SCENARIOS.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => run(s.name, async () => (await demoPlay(s.id), `${s.name} started`), true)}
                  className="w-full rounded-xl bg-ink px-5 py-4 text-left text-surface transition-[transform,opacity] hover:opacity-90 active:scale-[0.99] disabled:opacity-50"
                >
                  <span className="block font-semibold">{s.name}</span>
                  <span className="block text-meta opacity-80">{s.what}</span>
                </button>
              </li>
            ))}
            <li>
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => run("Reset", async () => (await demoReset(), "Reset: all cases and events cleared"))}
                className="w-full rounded-xl border border-line-strong px-5 py-4 text-left font-semibold transition-colors hover:bg-surface-2 disabled:opacity-50"
              >
                Reset the demo
              </button>
            </li>
          </ul>

          <h2 className="mt-8 text-lead font-semibold">Single events</h2>
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
        </section>

        <section aria-labelledby="cases-title" className="rounded-2xl border border-line bg-surface p-6">
          <h2 id="cases-title" className="text-lead font-semibold">
            Cases {cases ? <span className="text-ink-2 tabular">· {cases.length}</span> : null}
          </h2>
          <ul className="mt-4 divide-y divide-line" aria-live="polite">
            {cases?.length === 0 && <li className="py-3 text-ink-2">No cases yet. Play a scenario.</li>}
            {cases?.map((c) => (
              <li key={c.case_id} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-4">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{c.title}</p>
                  <p className="text-meta text-ink-2 tabular">
                    {c.case_number} · {c.status}
                    {c.threat ? ` · ${c.threat} (${c.confidence})` : ""}
                  </p>
                </div>
                <Link
                  href={`/guardian/${encodeURIComponent(c.case_id)}`}
                  className="rounded-full bg-ink px-4 py-2 font-semibold text-surface transition-opacity hover:opacity-90"
                >
                  Guardian
                </Link>
                <Link
                  href={`/case/${encodeURIComponent(c.case_id)}`}
                  className="rounded-full border border-line-strong px-4 py-2 font-semibold transition-colors hover:bg-surface-2"
                >
                  Maya’s view
                </Link>
              </li>
            ))}
          </ul>

          <h2 className="mt-8 text-lead font-semibold">Recent</h2>
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
      className="rounded-full border border-line-strong bg-surface px-5 py-3 font-semibold transition-colors hover:bg-surface-2 disabled:opacity-40"
    >
      {label}
    </button>
  );
}
