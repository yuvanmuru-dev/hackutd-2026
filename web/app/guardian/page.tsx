"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import "@/components/guardian/guardian.css";
import { GuardianScreen } from "@/components/guardian/GuardianScreen";
import { GuardianMark } from "@/components/guardian/GuardianMark";
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
    <main className="guardian flex flex-col items-start gap-5 p-6 sm:p-10">
      <GuardianMark size={40} />
      <h1 className="mt-6 text-balance text-[28px] font-semibold">
        {state === "looking" ? "Finding the latest case…" : "Waiting for a case"}
      </h1>
      {state === "none" && (
        <>
          <p className="max-w-xl text-[18px] text-[var(--g-ink-2)]">
            Titan opens a case the moment something risky happens on Maya’s account. Start a scenario from the demo
            console.
          </p>
          <button
            type="button"
            onClick={() => {
              setState("looking");
              look();
            }}
            className="h-12 rounded-[8px] border border-[var(--g-line-strong)] px-5 text-[16px] font-semibold text-[var(--g-ink)] transition-colors hover:bg-[var(--g-surface-2)]"
          >
            Check again
          </button>
        </>
      )}
    </main>
  );
}
