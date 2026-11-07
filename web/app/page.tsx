import Link from "next/link";
import { Wordmark } from "@/components/TGlyph";

const SCREENS = [
  { href: "/portal", name: "Account portal", what: "Maya's carrier account, with the pause screen" },
  { href: "/guardian", name: "Guardian", what: "The projector view: four agents working the case live" },
  { href: "/console", name: "Demo console", what: "Play the scenarios and send single events" },
];

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-3xl px-6 py-16">
      <Wordmark size={36} />
      <h1 className="mt-10 text-title font-semibold tracking-tight">Titan demo screens</h1>
      <p className="mt-3 text-lead text-ink-2">Pick the screen for this device.</p>
      <ul className="mt-10 flex flex-col gap-3">
        {SCREENS.map((s) => (
          <li key={s.href}>
            <Link
              href={s.href}
              className="block rounded-lg border border-line bg-surface px-6 py-5 transition-colors hover:border-line-strong hover:bg-surface-2"
            >
              <span className="block text-lead font-semibold">{s.name}</span>
              <span className="block text-ink-2">{s.what}</span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
