import Link from "next/link";
import type { ReactNode } from "react";

// Mock carrier account site. Neutral name and mark: no carrier branding in the UI (D-004).
export function PortalShell({ children, signedIn }: { children: ReactNode; signedIn?: boolean }) {
  return (
    <div className="flex min-h-screen flex-col bg-ground">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-18 w-full max-w-5xl items-center gap-4 px-5 sm:px-8">
          <Link href="/portal" className="flex items-center gap-3 rounded-md text-lead font-bold tracking-tight">
            <span aria-hidden className="grid h-10 w-10 place-items-center rounded-lg bg-ink text-[20px] font-black text-surface">
              M
            </span>
            My Mobile
          </Link>
          {signedIn && (
            <nav className="ml-auto flex items-center gap-6 text-body" aria-label="Account">
              <span className="hidden text-ink-2 sm:inline">Bill</span>
              <span className="hidden text-ink-2 sm:inline">Plan</span>
              <Link href="/portal/security" className="font-semibold text-ink underline-offset-4 hover:underline">
                Security
              </Link>
              <span className="grid h-10 w-10 place-items-center rounded-full bg-surface-2 font-semibold" title="Maya">
                M
              </span>
            </nav>
          )}
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-5 py-10 sm:px-8 sm:py-14">{children}</main>
    </div>
  );
}
