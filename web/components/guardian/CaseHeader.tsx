import { TGlyph } from "@/components/TGlyph";
import type { Contract as C } from "@/lib/api/client";
import type { GuardianView } from "./derive";

const STATUS: Record<C.Case["status"], { text: string; tone: string }> = {
  open: { text: "Titan is on it", tone: "live" },
  awaiting_reply: { text: "Waiting for Maya", tone: "notice" },
  recovering: { text: "Recovering", tone: "notice" },
  watching: { text: "Safe · watching 24 h", tone: "positive" },
  closed: { text: "Closed", tone: "neutral" },
};

type Props = {
  detail: C.CaseDetail | null;
  head: C.Case | null;
  view: GuardianView;
  mode: "live" | "replay" | "loading";
};

export function CaseHeader({ detail, head, view, mode }: Props) {
  const status = head?.status ?? detail?.status ?? "open";
  const s = STATUS[status];
  const name = detail?.user.name ?? "Maya";
  return (
    <header className="flex items-center gap-6">
      <div className="flex items-center gap-3">
        <TGlyph size={40} tone="accent" title="Titan" />
        <span className="text-[22px] font-semibold tracking-tight">Titan Guardian</span>
      </div>
      <div className="h-8 w-px bg-[var(--g-line)]" aria-hidden />
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[28px] font-semibold leading-tight tracking-tight">
          {name} · {head?.title ?? detail?.title ?? "Loading case"}
        </h1>
        <p className="g-label tabular">
          Case {head?.case_number ?? detail?.case_number ?? "…"}
          {view.systemLine ? ` · ${view.systemLine.title}` : ""}
        </p>
      </div>
      <span className="g-pill" data-tone={s.tone}>
        {s.text}
      </span>
      {mode === "live" && (
        <span className="g-pill" data-tone="live">
          <span className="g-dot" aria-hidden />
          Live
        </span>
      )}
      {mode === "replay" && (
        <span className="g-pill" title="The brain is not reachable; showing a recorded run">
          Replay
        </span>
      )}
    </header>
  );
}
