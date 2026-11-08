import type { Contract as C } from "@/lib/api/client";

const fmt = (v: C.Signal["value"]) =>
  v === null ? "—" : typeof v === "boolean" ? (v ? "yes" : "no") : String(v);

export function DataUsed({ dataUsed, signals }: { dataUsed: string[]; signals: C.Signal[] }) {
  return (
    <section className="g-panel flex min-h-0 flex-col px-6 py-5" aria-label="Data used">
      <h2 className="text-[22px] font-semibold">Data used</h2>
      <div className="g-scroll mt-3 min-h-0 flex-1">
        <ul className="flex flex-col gap-2 leading-snug">
          {dataUsed.length === 0 && <li className="text-[var(--g-ink-3)]">None listed yet</li>}
          {dataUsed.map((d) => (
            <li key={d}>{d}</li>
          ))}
        </ul>
        {signals.length > 0 && (
          <>
            <p className="g-label mt-4">Signals and their sources</p>
            <ul className="mt-1 flex flex-col gap-1 text-[17px] leading-snug text-[var(--g-ink-2)]">
              {signals.slice(0, 8).map((s) => (
                <li key={`${s.group}.${s.name}`}>
                  {s.name.charAt(0).toUpperCase() + s.name.slice(1).replace(/_/g, " ")}: <span className="tabular text-[var(--g-ink)]">{fmt(s.value)}</span>
                  {s.baseline !== undefined && s.baseline !== null && <> (usual {fmt(s.baseline)})</>}
                  <span className="text-[var(--g-ink-3)]"> · {s.source.name}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
      <p className="mt-4 border-t border-[var(--g-line)] pt-3 font-semibold">
        Never used: call audio, location history, contacts
      </p>
    </section>
  );
}
