"use client";

import "./guardian.css";
import { useMemo } from "react";
import { AgentPipeline } from "./AgentPipeline";
import { CallBar } from "./CallBar";
import { CaseHeader } from "./CaseHeader";
import { ConversationStrip } from "./ConversationStrip";
import { DataUsed } from "./DataUsed";
import { deriveView } from "./derive";
import { RecoveryChecklist } from "./RecoveryChecklist";
import { VerdictCard } from "./VerdictCard";
import { useGuardianCase } from "./useGuardianCase";

export function GuardianScreen({ caseId }: { caseId: string | null }) {
  const { detail, head, steps, mode } = useGuardianCase(caseId);
  const view = useMemo(() => deriveView(detail, steps), [detail, steps]);

  return (
    <div className="guardian flex h-screen min-h-[860px] flex-col gap-4 overflow-hidden p-7">
      <CaseHeader detail={detail} head={head} view={view} mode={mode} />
      <CallBar call={detail?.call ?? null} markers={view.callMarkers} live={mode === "live"} />
      <div className="grid min-h-0 flex-[1.35] grid-cols-[minmax(0,1fr)_clamp(340px,24vw,460px)] grid-rows-[minmax(0,1fr)] gap-4">
        <AgentPipeline view={view} />
        <VerdictCard detail={detail} head={head} view={view} />
      </div>
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)_minmax(0,0.9fr)] grid-rows-[minmax(0,1fr)] gap-4">
        <ConversationStrip messages={detail?.messages ?? []} />
        <RecoveryChecklist actions={detail?.actions ?? []} view={view} />
        <DataUsed dataUsed={detail?.data_used ?? []} signals={detail?.signals ?? []} />
      </div>
    </div>
  );
}
