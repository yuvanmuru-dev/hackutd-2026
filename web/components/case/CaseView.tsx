"use client";

import { productCase } from "@/lib/copy";
import { useCallback, useEffect, useState } from "react";
import { Wordmark } from "@/components/TGlyph";
import { BTN_DARK } from "@/components/ui";
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
        if (s.type === "summary" || s.type === "done" || s.type === "action")
          load();
      },
      () => {},
    );
  }, [caseId, load]);

  const s = detail?.summary ?? null;
  const applied = (detail?.actions ?? []).filter(
    (a) => a.status === "applied" || a.status === "approved",
  );

  return (
    <main className="mx-auto w-full max-w-[720px] px-5 pt-8 pb-16 sm:px-8 sm:pt-10">
      <div className="flex items-center gap-3">
        <Wordmark size={24} />
        {detail && (
          <span className="ml-auto text-[15px] text-ink-3 tabular">
            Case {detail.case_number}
          </span>
        )}
      </div>

      {missing && !detail && (
        <section className="mt-10 border-l-4 border-notice pl-5">
          <h1 className="text-title font-semibold tracking-[-0.01em]">
            We can’t open this case right now
          </h1>
          <p className="mt-3 text-lead text-ink-2">
            Your account is still protected. Try again in a minute.
          </p>
          <button type="button" onClick={load} className={`mt-6 ${BTN_DARK}`}>
            Try again
          </button>
        </section>
      )}

      {!detail && !missing && <CaseSkeleton />}

      {detail && !s && (
        <section className="mt-8">
          <h1 className="text-balance text-title font-bold tracking-[-0.01em]">
            Titan is still working on this
          </h1>
          <p className="mt-4 text-lead text-ink-2">
            {detail.title}. You’ll get a summary here and by text.
          </p>
          {applied.length > 0 && (
            <Block title="Done so far" className="mt-8 border-t border-line">
              <Checklist items={applied.map((a) => a.description)} />
            </Block>
          )}
        </section>
      )}

      {detail && s && (
        <article>
          <h1 className="mt-8 text-balance text-title font-bold tracking-[-0.01em]">
            Here’s what happened
          </h1>
          <dl className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 border-y border-line py-3 text-body">
            <dt className="text-ink-3">Status</dt>
            <dd
              className={`inline-flex h-6 items-center rounded-full px-2.5 text-[14px] font-semibold ${statusTone(detail.status)}`}
            >
              {statusWords(detail.status)}
            </dd>
            {detail.status === "watching" && (
              <dd className="text-ink-2">
                Titan is watching for 24 hours
              </dd>
            )}
          </dl>
          <p className="mt-6 text-lead">{productCase(s.what_happened)}</p>

          <div className="mt-8 divide-y divide-line border-t border-line">
            <Block title="Why Titan stepped in">
              <p>{productCase(s.why_we_stepped_in)}</p>
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
              <ol className="flex list-decimal flex-col gap-3 pl-6 marker:font-semibold marker:text-ink-2">
                {s.next_steps.map((n) => (
                  <li key={n} className="pl-1">
                    {productCase(n)}
                  </li>
                ))}
              </ol>
            </Block>

            <div className="py-7">
              <section className="border-l-4 border-accent py-1 pl-5">
                <h2 className="text-[20px] font-semibold">Spot it next time</h2>
                <p className="mt-2 text-body">{productCase(s.spot_it_next_time)}</p>
              </section>
            </div>

            {s.replies.length > 0 && (
              <Block title="Reply to Titan’s text with">
                <dl className="grid grid-cols-[auto_1fr] items-baseline gap-x-5 gap-y-3">
                  {s.replies.map((r) => (
                    <div key={r.keyword} className="contents">
                      <dt className="font-semibold" translate="no">
                        <code className="rounded-[4px] bg-surface-2 px-1.5 py-0.5 font-sans text-[16px] font-semibold">
                          {r.keyword}
                        </code>
                      </dt>
                      <dd className="text-ink-2">{r.meaning}</dd>
                    </div>
                  ))}
                </dl>
              </Block>
            )}

            {s.data_we_looked_at.length > 0 && (
              <Block title="Information Titan used">
                <ul className="flex flex-col gap-2 text-ink-2">
                  {s.data_we_looked_at.map((d) => (
                    <li key={d}>{d}</li>
                  ))}
                </ul>
                <p className="mt-3 text-ink-2">
                  Titan never uses your call audio, messages, contacts or
                  location.
                </p>
              </Block>
            )}
          </div>
        </article>
      )}
      <footer className="mt-14 border-t border-line pt-6 text-[14px] text-ink-3">
        Hackathon prototype built for the T-Mobile track; not affiliated with or
        endorsed by T-Mobile.
      </footer>
    </main>
  );
}

/** Same shape as the loaded page, so the first paint already reads as "your case". */
function CaseSkeleton() {
  const bar = "bg-surface-2 motion-safe:animate-pulse";
  return (
    <div className="mt-8" role="status" aria-label="Opening your case">
      <div className={`h-8 w-3/5 rounded-[6px] ${bar}`} />
      <div className="mt-4 border-y border-line py-3">
        <div className={`h-6 w-40 rounded-full ${bar}`} />
      </div>
      <div className={`mt-6 h-6 w-full rounded-[6px] ${bar}`} />
      <div className={`mt-2 h-6 w-11/12 rounded-[6px] ${bar}`} />
      <div className={`mt-2 h-6 w-3/5 rounded-[6px] ${bar}`} />
      {[0, 1].map((i) => (
        <div
          key={i}
          className={`border-t border-line pt-7 ${i === 0 ? "mt-8" : "mt-7"}`}
        >
          <div className={`h-6 w-48 rounded-[6px] ${bar}`} />
          <div className={`mt-4 h-5 w-full rounded-[6px] ${bar}`} />
          <div className={`mt-2 h-5 w-4/5 rounded-[6px] ${bar}`} />
        </div>
      ))}
    </div>
  );
}

function statusWords(status: C.CaseDetail["status"]) {
  switch (status) {
    case "watching":
      return "Safe";
    case "closed":
      return "Closed";
    case "recovering":
      return "Recovering";
    case "awaiting_reply":
      return "Waiting for your reply";
    default:
      return "In progress";
  }
}

/** Green only for the safe state; amber while Titan or the customer still has work to do. */
function statusTone(status: C.CaseDetail["status"]) {
  switch (status) {
    case "watching":
      return "bg-positive-soft text-positive";
    case "closed":
      return "bg-surface-2 text-ink-2";
    default:
      return "bg-notice-soft text-notice";
  }
}

function Block({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`py-7 ${className}`}>
      <h2 className="text-[20px] font-semibold">{title}</h2>
      <div className="mt-3 text-body">{children}</div>
    </section>
  );
}

function Checklist({ items }: { items: string[] }) {
  return (
    <ul className="flex flex-col gap-3">
      {items.map((t) => (
        <li key={t} className="flex gap-3">
          <svg
            aria-hidden
            viewBox="0 0 16 16"
            width="20"
            height="20"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="mt-1 flex-none text-positive"
          >
            <path d="m3.5 8.5 3 3 6-7" />
          </svg>
          {productCase(t)}
        </li>
      ))}
    </ul>
  );
}
