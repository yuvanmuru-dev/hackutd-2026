import Link from "next/link";
import type { ReactNode } from "react";
import { TGlyph } from "@/components/TGlyph";

// `key` is the legacy name pages pass as `current`; either the key or the label marks the active tab.
const SECTIONS = [
  { key: "Overview", label: "Account", href: null },
  { key: "Bill", label: "Billing", href: null },
  { key: "Plan", label: "Plans and devices", href: null },
  { key: "Security", label: "Privacy and security", href: "/portal/security" },
] as const;

type Section = (typeof SECTIONS)[number];

// Maya's carrier account site (mock). Official T-Mobile T (D-044).
export function PortalShell({
  children,
  signedIn,
  current,
}: {
  children: ReactNode;
  signedIn?: boolean;
  current?: Section["key"] | Section["label"];
}) {
  return (
    <div className="flex min-h-screen flex-col bg-ground">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-[72px] w-full max-w-5xl items-center gap-4 px-5 sm:px-8">
          <Link href="/portal" className="flex items-center gap-3 rounded-md" aria-label="My account home">
            <TGlyph size={40} title="" />
            <span className="text-[18px] font-semibold">My account</span>
          </Link>
          <div className="ml-auto flex items-center gap-4">
            <span className="hidden text-[15px] text-ink-2 sm:inline">Help</span>
            {signedIn && (
              <>
                <span className="hidden text-body text-ink-2 sm:inline">Maya</span>
                <span
                  aria-hidden
                  className="grid h-11 w-11 place-items-center rounded-full bg-surface-2 text-body font-semibold text-ink"
                >
                  M
                </span>
              </>
            )}
          </div>
        </div>
        {signedIn && (
          <nav aria-label="Account sections" className="mx-auto w-full max-w-5xl overflow-x-auto px-5 sm:px-8">
            <ul className="flex gap-7">
              {SECTIONS.map((s) => {
                const active = current === s.key || current === s.label;
                return (
                  <li key={s.key} className={s.href ? "shrink-0" : "hidden shrink-0 sm:block"}>
                    {s.href ? (
                      <Link
                        href={s.href}
                        aria-current={active ? "page" : undefined}
                        className={`inline-flex h-12 items-center whitespace-nowrap border-b-[3px] text-body font-medium transition-colors ${
                          active ? "border-accent text-ink" : "border-transparent text-ink-2 hover:text-ink"
                        }`}
                      >
                        {s.label}
                      </Link>
                    ) : (
                      <span className="inline-flex h-12 items-center whitespace-nowrap border-b-[3px] border-transparent text-body font-medium text-ink-2">
                        {s.label}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          </nav>
        )}
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-5 py-8 sm:px-8 sm:py-10">{children}</main>
      <footer className="border-t border-line bg-surface">
        <div className="mx-auto w-full max-w-5xl px-5 py-6 text-[14px] text-ink-3 sm:px-8">
          <p>Demo account · Titan prototype</p>
          <p className="mt-1">
            Hackathon prototype built for the T-Mobile track; not affiliated with or endorsed by T-Mobile.
          </p>
        </div>
      </footer>
    </div>
  );
}
