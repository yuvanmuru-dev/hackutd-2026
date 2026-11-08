import Link from "next/link";
import type { ReactNode } from "react";
import { TGlyph } from "@/components/TGlyph";

const SECTIONS = ["Overview", "Bill", "Plan", "Security"] as const;

// Maya's carrier account site (mock). Official T-Mobile T (D-044).
export function PortalShell({
  children,
  signedIn,
  current,
}: {
  children: ReactNode;
  signedIn?: boolean;
  current?: (typeof SECTIONS)[number];
}) {
  return (
    <div className="flex min-h-screen flex-col bg-ground">
      <header className="bg-surface shadow-[0_1px_0_var(--line)]">
        <div className="mx-auto flex h-[72px] w-full max-w-5xl items-center gap-4 px-5 sm:px-8">
          <Link href="/portal" className="flex items-center gap-3 rounded-md" aria-label="My account home">
            <TGlyph size={40} title="" />
            <span className="text-[20px] font-extrabold tracking-[-0.02em]">My account</span>
          </Link>
          {signedIn && (
            <div className="ml-auto flex items-center gap-3">
              <span className="hidden text-body text-ink-2 sm:inline">Maya</span>
              <span
                aria-hidden
                className="grid h-11 w-11 place-items-center rounded-full bg-accent-soft text-body font-bold text-accent-text"
              >
                M
              </span>
            </div>
          )}
        </div>
        {signedIn && (
          <nav aria-label="Account sections" className="mx-auto w-full max-w-5xl overflow-x-auto px-5 sm:px-8">
            <ul className="flex gap-7">
              {SECTIONS.map((s) => {
                const active = s === current;
                return (
                  <li key={s}>
                    {s === "Security" ? (
                      <Link
                        href="/portal/security"
                        aria-current={active ? "page" : undefined}
                        className={`inline-flex h-12 items-center border-b-[3px] text-body font-semibold transition-colors ${
                          active ? "border-accent text-ink" : "border-transparent text-ink-2 hover:text-ink"
                        }`}
                      >
                        {s}
                      </Link>
                    ) : (
                      <span className="inline-flex h-12 items-center border-b-[3px] border-transparent text-body text-ink-3">
                        {s}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          </nav>
        )}
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-5 py-10 sm:px-8 sm:py-14">{children}</main>
      <footer className="border-t border-line bg-surface">
        <p className="mx-auto w-full max-w-5xl px-5 py-6 text-meta text-ink-2 sm:px-8">
          Hackathon prototype built for the T-Mobile track; not affiliated with or endorsed by T-Mobile.
        </p>
      </footer>
    </div>
  );
}
