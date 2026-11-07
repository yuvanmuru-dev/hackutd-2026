"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import "@/components/guardian/guardian.css";
import { GuardianScreen } from "@/components/guardian/GuardianScreen";
import { TGlyph } from "@/components/TGlyph";
import { getCases } from "@/lib/api/client";

type State = "looking" | "none" | "down";

// Opens the most recently updated case. No polling: "Check again" asks once.
export default function GuardianIndex() {
  const router = useRouter();
  const [state, setState] = useState<State>("looking");

  const look = useCallback(() => {
    getCases()
      .then((cases) => {
        if (cases.length === 0) return setState("none");
        const latest = [...cases].sort((a, b) => b.updated_at.localeCompare(a.updated_at))[0];
        router.replace(`/guardian/${encodeURIComponent(latest.case_id)}`);
      })
      .catch(() => setState("down"));
  }, [router]);

  useEffect(() => {
    look();
  }, [look]);

  if (state === "down") return <GuardianScreen caseId={null} />;

  return (
    <main className="guardian flex flex-col items-center justify-center gap-6 p-8 text-center">
      <TGlyph size={64} tone="accent" title="Titan" />
      <h1 className="text-balance text-[36px] font-semibold tracking-tight">
        {state === "looking" ? "Finding the latest case…" : "Waiting for a case"}
      </h1>
      {state === "none" && (
        <>
          <p className="max-w-xl text-[22px] text-[var(--g-ink-2)]">
            Titan opens a case the moment something risky happens on Maya’s account. Start a scenario from the demo
            console.
          </p>
          <button
            type="button"
            onClick={() => {
              setState("looking");
              look();
            }}
            className="h-14 rounded-full bg-[var(--g-ink)] px-8 text-[20px] font-semibold text-[var(--g-ground)] transition-[transform,opacity] hover:opacity-90 active:scale-[0.98]"
          >
            Check again
          </button>
        </>
      )}
    </main>
  );
}
