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
    <div className="guardian flex min-h-screen flex-col gap-4 p-4 sm:p-7 2xl:h-screen 2xl:min-h-[860px] 2xl:overflow-hidden">
      <CaseHeader detail={detail} head={head} view={view} mode={mode} />
      <CallBar call={detail?.call ?? null} markers={view.callMarkers} live={mode === "live"} />
      <div className="grid min-h-0 grid-cols-1 gap-4 lg:h-[600px] lg:grid-cols-[minmax(0,1fr)_clamp(340px,24vw,460px)] lg:grid-rows-[minmax(0,1fr)] 2xl:h-auto 2xl:flex-[1.35]">
        <AgentPipeline view={view} />
        <VerdictCard detail={detail} head={head} view={view} />
      </div>
      <div className="grid min-h-0 grid-cols-1 gap-4 lg:h-[380px] lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)_minmax(0,0.9fr)] lg:grid-rows-[minmax(0,1fr)] 2xl:h-auto 2xl:flex-1">
        <ConversationStrip messages={detail?.messages ?? []} />
        <RecoveryChecklist actions={detail?.actions ?? []} view={view} />
        <DataUsed dataUsed={detail?.data_used ?? []} signals={detail?.signals ?? []} />
      </div>
    </div>
  );
}
