import type { Contract as C } from "@/lib/api/client";
import type { GuardianView } from "./derive";

const ORDER: Record<C.Action["status"], number> = {
  applied: 0,
  approved: 1,
  awaiting_approval: 2,
  proposed: 3,
  rejected: 4,
  failed: 5,
};

const MARK: Record<C.Action["status"], string> = {
  applied: "✓",
  approved: "✓",
  awaiting_approval: "?",
  proposed: "",
  rejected: "–",
  failed: "!",
};

const VIA: Record<NonNullable<C.Action["approved_via"]>, string> = { web: "on the web", sms: "by text", voice: "on the call" };
const approved = (a: C.Action) => (a.approved_via ? `Maya approved ${VIA[a.approved_via]}` : "Maya approved");

function note(a: C.Action): string {
  switch (a.status) {
    case "applied":
      return a.requires_approval ? approved(a) : "Done on its own · safer";
    case "approved":
      return approved(a);
    case "awaiting_approval":
      return "Waiting for Maya’s yes";
    case "proposed":
      return "Proposed";
    case "rejected":
      return "Maya said no";
    case "failed":
      return "Didn’t go through";
  }
}

export function RecoveryChecklist({ actions, view }: { actions: C.Action[]; view: GuardianView }) {
  const rows = [...actions].sort((a, b) => ORDER[a.status] - ORDER[b.status] || a.created_at.localeCompare(b.created_at));
  const done = actions.filter((a) => a.status === "applied" || a.status === "approved").length;

  return (
    <section className="g-panel flex min-h-0 flex-col px-6 py-5" aria-label="What Titan did">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-[22px] font-semibold">What Titan did</h2>
        {actions.length > 0 && (
          <span className="g-label tabular">
            {done} of {actions.length} done
          </span>
        )}
      </div>
      <ul className="g-scroll mt-3 flex min-h-0 flex-1 flex-col gap-3" aria-live="polite">
        {rows.length === 0 && (
          <li className="text-[var(--g-ink-3)]">{view.needsApproval ? "Waiting for Maya’s answers" : "No actions yet"}</li>
        )}
        {rows.map((a) => (
          <li key={a.action_id} className="flex items-start gap-3">
            <span className="g-check mt-0.5" data-status={a.status} aria-hidden>
              {MARK[a.status]}
            </span>
            <div className="min-w-0">
              <p
                className="leading-snug"
                style={a.status === "rejected" ? { color: "var(--g-ink-3)", textDecoration: "line-through" } : undefined}
              >
                {a.description}
              </p>
              <p className="g-label">{note(a)}</p>
            </div>
          </li>
        ))}
        {view.approvals.some((s) => s.title.startsWith("Declined")) && (
          <li className="g-label">
            {view.approvals
              .filter((s) => s.title.startsWith("Declined"))
              .map((s) => s.title)
              .join(" · ")}
          </li>
        )}
      </ul>
    </section>
  );
}
