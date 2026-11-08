"use client";

import { useEffect, useRef } from "react";
import type { Contract as C } from "@/lib/api/client";
import { AgentPipeline } from "./AgentPipeline";
import { DataUsed } from "./DataUsed";
import type { GuardianView } from "./derive";
import { RecoveryChecklist } from "./RecoveryChecklist";
import { VerdictCard } from "./VerdictCard";

type Props = { detail: C.CaseDetail | null; head: C.Case | null; view: GuardianView; onClose: () => void };

// For the judges who ask "how did it decide?": the four agents' steps, the verdict and its reasons,
// every action, and the data used (and never used). Opened with D or the Details button; D (the screen's toggle), Esc or Close closes it.
export function DetailDrawer({ detail, head, view, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    // "close" is dispatched as a task, so a close from a re-mount can arrive after the dialog reopened:
    // only a dialog that is really closed means the viewer closed it.
    const closed = () => {
      if (!d.open) onClose();
    };
    d.addEventListener("close", closed);
    if (!d.open) d.showModal();
    return () => {
      d.removeEventListener("close", closed);
      d.close();
    };
  }, [onClose]);
  return (
    <dialog
      ref={ref}
      aria-labelledby="drawer-title"
      className="g-drawer"
    >
      <div className="g-drawer-head">
        <h2 id="drawer-title" className="g-drawer-title">
          How Titan decided
        </h2>
        <button type="button" className="g-key" onClick={onClose}>
          Close <kbd>D</kbd>
        </button>
      </div>
      <div className="g-drawer-body">
        <AgentPipeline view={view} all />
        <div className="g-drawer-grid">
          <VerdictCard detail={detail} head={head} view={view} />
          <RecoveryChecklist actions={detail?.actions ?? []} view={view} />
          <DataUsed dataUsed={detail?.data_used ?? []} risk={detail?.risk ?? null} />
        </div>
      </div>
    </dialog>
  );
}
