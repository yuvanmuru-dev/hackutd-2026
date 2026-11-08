import type { Contract as C } from "@/lib/api/client";
import { confidenceWords, wordsFor, type GuardianView } from "./derive";

type Props = { detail: C.CaseDetail | null; head: C.Case | null; view: GuardianView };

export function VerdictCard({ detail, head, view }: Props) {
  const risk = detail?.risk ?? null;
  const threat = risk?.threat ?? head?.threat ?? null;
  const revealed = view.verdictRevealed && !!threat;
  const v = detail?.verification ?? null;
  const reasons = (risk?.top_reasons ?? []).filter((r) => r.contribution > 0).slice(0, 3);
  const counter = (risk?.top_reasons ?? []).find((r) => r.contribution < 0);

  return (
    <section className="g-panel g-verdict flex min-h-0 flex-col overflow-hidden px-6 py-5" data-revealed={revealed} aria-live="polite" aria-label="Verdict">
      <h2 className="g-verdict-threat text-balance">{revealed ? wordsFor(threat) : "Scoring…"}</h2>
      <p className="mt-2 text-[18px] font-semibold tabular text-[var(--g-ink-2)]">
        {revealed ? confidenceWords(risk, head) : "The Risk agent has not scored yet"}
      </p>

      {revealed && reasons.length > 0 && (
        <div className="g-scroll min-h-0 flex-1">
          <p className="g-label mt-5">Top reasons</p>
          <ul className="mt-1 divide-y divide-[var(--g-line)] leading-snug [&>li]:py-2">
            {reasons.map((r) => (
              <li key={r.feature}>{r.text}</li>
            ))}
          </ul>
          {counter && <p className="mt-3 leading-snug text-[var(--g-ink-2)]">Against it: {counter.text}</p>}
        </div>
      )}

      <div className="mt-auto flex-none pt-4">
        {v ? (
          <span className="g-pill" data-tone={v.status === "verified" ? "positive" : "notice"}>
            {v.status === "verified" ? "Verified" : "Confidence reduced"} · {v.claims_checked} claims,{" "}
            {v.claims_dropped} dropped
          </span>
        ) : (
          <span className="g-pill">{view.verified ? "Verified" : "Verification pending"}</span>
        )}
      </div>
    </section>
  );
}
