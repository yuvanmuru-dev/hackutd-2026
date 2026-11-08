// What this account page is for, in T-Mobile's own product words. Static and true for every line.
// Sits beside the sign-in and consent panels on wide screens, the way carrier sign-in pages pair the form
// with one column of plain information.
const PROTECT: [string, string][] = [
  ["SIM Protection", "Prevents your number from being moved to another SIM or device."],
  ["Port Out Protection", "Blocks unauthorized transfers of your line to another wireless carrier."],
  ["Transfer PIN", "Needed only when you move your number to another carrier."],
];

export function ProtectAside() {
  return (
    <section aria-labelledby="protect-title" className="max-w-[560px] lg:pt-2">
      <h2 id="protect-title" className="text-[20px] font-semibold leading-7">
        Protect your number
      </h2>
      <p className="mt-1.5 text-[16px] leading-6 text-ink-2">
        These free features are under Privacy and security once you sign in.
      </p>
      <dl className="mt-5 divide-y divide-line border-y border-line">
        {PROTECT.map(([name, what]) => (
          <div key={name} className="py-4">
            <dt className="text-body font-semibold">{name}</dt>
            <dd className="mt-0.5 text-[16px] leading-6 text-ink-2">{what}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-5 text-[16px] leading-6 text-ink-2">
        T-Mobile will never call and ask you to turn off a protection or share a PIN.
      </p>
    </section>
  );
}

/** Two columns on wide screens: the task panel, then the aside. */
export const SPLIT = "grid grid-cols-1 items-start gap-8 lg:grid-cols-[minmax(0,560px)_minmax(0,1fr)] lg:gap-16";
