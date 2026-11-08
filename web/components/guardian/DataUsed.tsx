import type { Contract as C } from "@/lib/api/client";

export function DataUsed({ dataUsed, risk }: { dataUsed: string[]; risk: C.RiskScore | null }) {
  return (
    <section className="g-panel flex min-h-0 flex-col px-6 py-5" aria-label="Data used">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-[20px] font-semibold">Data used</h2>
        {risk && (
          <span className="g-label tabular">
            Risk model: <span className="text-[var(--g-ink)]">{risk.model}</span>
            {risk.calibrated ? " · calibrated" : ""}
          </span>
        )}
      </div>
      <div className="g-scroll mt-3 min-h-0 flex-1">
        <ul className="divide-y divide-[var(--g-line)] leading-snug [&>li]:py-1.5">
          {dataUsed.length === 0 && <li className="text-[var(--g-ink-3)]">None listed yet</li>}
          {dataUsed.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
      </div>
      <p className="mt-4 border-t border-[var(--g-line)] pt-3 font-semibold">
        Never used: call audio, location history, contacts
      </p>
    </section>
  );
}
