"use client";

import { useCallback, useEffect, useState } from "react";
import { TGlyph } from "@/components/TGlyph";
import { getCase, subscribeCase, type Contract as C } from "@/lib/api/client";

// Maya's own view of the incident ("the T-Life app view"). Light, calm, mobile-first. No links (D-012).
export function CaseView({ caseId }: { caseId: string }) {
  const [detail, setDetail] = useState<C.CaseDetail | null>(null);
  const [missing, setMissing] = useState(false);

  const load = useCallback(() => {
    getCase(caseId)
      .then((d) => {
        setDetail(d);
        setMissing(false);
      })
      .catch(() => setMissing(true));
  }, [caseId]);

  useEffect(() => {
    load();
    // Refresh once when the run writes its summary or finishes; no polling.
    return subscribeCase(
      caseId,
      (s) => {
        if (s.type === "summary" || s.type === "done" || s.type === "action") load();
      },
      () => {},
    );
  }, [caseId, load]);

  const s = detail?.summary ?? null;
  const applied = (detail?.actions ?? []).filter((a) => a.status === "applied" || a.status === "approved");

  return (
    <main className="mx-auto w-full max-w-2xl px-5 pt-8 pb-16 sm:px-8 sm:pt-14">
      <div className="flex items-center gap-3">
        <TGlyph size={36} />
        <span className="text-lead font-semibold">Titan</span>
        {detail && <span className="ml-auto text-ink-2 tabular">Case {detail.case_number}</span>}
      </div>

      {missing && !detail && (
        <section className="mt-10 rounded-2xl bg-surface p-7">
          <h1 className="text-title font-semibold tracking-tight">We can’t open this case right now</h1>
          <p className="mt-3 text-lead text-ink-2">Your account is still protected. Try again in a minute.</p>
          <button
            type="button"
            onClick={load}
            className="mt-6 h-14 rounded-full bg-ink px-8 text-lead font-semibold text-surface transition-transform hover:opacity-90 active:scale-[0.98]"
          >
            Try again
          </button>
        </section>
      )}

      {!detail && !missing && <p className="mt-10 text-lead text-ink-2">Opening your case…</p>}

      {detail && !s && (
        <section className="mt-10">
          <h1 className="text-balance text-title font-semibold tracking-tight">Titan is still working on this</h1>
          <p className="mt-3 text-lead text-ink-2">{detail.title}. You’ll get a summary here and by iMessage.</p>
          {applied.length > 0 && (
            <Block title="Done so far">
              <Checklist items={applied.map((a) => a.description)} />
            </Block>
          )}
        </section>
      )}

      {detail && s && (
        <article className="mt-10">
          <p className="inline-flex min-h-9 items-center rounded-2xl bg-positive-soft px-4 py-1.5 font-semibold text-positive">
            {statusWords(detail.status)}
          </p>
          <h1 className="mt-5 text-balance text-[clamp(28px,6vw,40px)] font-bold leading-tight tracking-tight">
            Here’s what happened
          </h1>
          <p className="mt-4 text-lead">{s.what_happened}</p>

          <Block title="Why Titan stepped in">
            <p>{s.why_we_stepped_in}</p>
            <p className="mt-3 text-ink-2">{s.confidence_text}</p>
          </Block>

          <Block title="What Titan did">
            <Checklist items={s.what_we_did} />
          </Block>

          {s.you_approved.length > 0 && (
            <Block title="What you approved">
              <Checklist items={s.you_approved} />
            </Block>
          )}

          <Block title="What to do next">
            <ul className="flex flex-col gap-3">
              {s.next_steps.map((n) => (
                <li key={n} className="flex gap-3">
                  <span aria-hidden className="mt-[11px] h-2 w-2 flex-none rounded-full bg-accent" />
                  {n}
                </li>
              ))}
            </ul>
          </Block>

          <section className="mt-8 rounded-2xl bg-accent-soft p-6">
            <h2 className="text-lead font-semibold">Spot it next time</h2>
            <p className="mt-2">{s.spot_it_next_time}</p>
          </section>

          {s.replies.length > 0 && (
            <Block title="Reply to Titan’s message with">
              <dl className="grid grid-cols-[auto_1fr] gap-x-5 gap-y-3">
                {s.replies.map((r) => (
                  <div key={r.keyword} className="contents">
                    <dt className="font-bold tracking-wide" translate="no">
                      {r.keyword}
                    </dt>
                    <dd className="text-ink-2">{r.meaning}</dd>
                  </div>
                ))}
              </dl>
            </Block>
          )}

          {s.data_we_looked_at.length > 0 && (
            <Block title="What Titan looked at">
              <ul className="flex flex-col gap-2 text-ink-2">
                {s.data_we_looked_at.map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
              <p className="mt-3 text-ink-2">Never: your call audio, your messages, your contacts or where you’ve been.</p>
            </Block>
          )}
        </article>
      )}
    </main>
  );
}

function statusWords(status: C.CaseDetail["status"]) {
  switch (status) {
    case "watching":
      return "You’re safe · Titan is watching for 24 hours";
    case "closed":
      return "Closed";
    case "recovering":
      return "Finishing your recovery";
    case "awaiting_reply":
      return "Waiting for your reply";
    default:
      return "Titan is on it";
  }
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-8 rounded-2xl bg-surface p-6">
      <h2 className="text-lead font-semibold">{title}</h2>
      <div className="mt-3 text-body">{children}</div>
    </section>
  );
}

function Checklist({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-col gap-3">
      {items.map((t) => (
        <li key={t} className="flex gap-3">
          <span
            aria-hidden
            className="mt-0.5 grid h-7 w-7 flex-none place-items-center rounded-full bg-positive text-[15px] font-bold text-surface"
          >
            ✓
          </span>
          {t}
        </li>
      ))}
    </ul>
  );
}
