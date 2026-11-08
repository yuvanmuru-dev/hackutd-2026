"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getCase, subscribeCase, type Contract as C } from "@/lib/api/client";
import fixture from "@/lib/fixtures/case.t2.json";
import { shouldRefetch } from "./derive";

export type GuardianMode = "loading" | "live" | "replay";

const FIXTURE = fixture as unknown as C.CaseDetail;

const headOf = (d: C.CaseDetail): C.Case => ({
  case_id: d.case_id,
  case_number: d.case_number,
  user_id: d.user_id,
  title: d.title,
  status: d.status,
  threat: d.threat,
  confidence: d.confidence,
  created_at: d.created_at,
  updated_at: d.updated_at,
});

/**
 * GET /cases/{id} once, then SSE. Steps drive state; CaseDetail is re-fetched once per step whose
 * type is in REFETCH_TYPES (coalesced while one is in flight). Never a polling loop (D-028, D-036).
 * Brain unreachable or case gone (brain restart wipes the store) -> the T2 fixture, labelled Replay.
 */
export function useGuardianCase(caseId: string | null) {
  const [detail, setDetail] = useState<C.CaseDetail | null>(null);
  const [head, setHead] = useState<C.Case | null>(null);
  const [steps, setSteps] = useState<C.StepEvent[]>([]);
  const [mode, setMode] = useState<GuardianMode>("loading");
  const inFlight = useRef(false);
  const dirty = useRef(false);
  const alive = useRef(true);

  const replay = useCallback(() => {
    if (!alive.current) return;
    setDetail(FIXTURE);
    setHead(headOf(FIXTURE));
    setSteps(FIXTURE.steps);
    setMode("replay");
  }, []);

  const refetch = useCallback(async (id: string) => {
    if (inFlight.current) {
      dirty.current = true;
      return;
    }
    inFlight.current = true;
    try {
      do {
        dirty.current = false;
        const d = await getCase(id);
        if (!alive.current) return;
        setDetail(d);
        // The stream closes on "done" before its trailing `case` event, so the head also follows refetches.
        setHead(headOf(d));
      } while (dirty.current);
    } catch {
      /* keep the last good detail; the stream keeps going */
    } finally {
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    if (!caseId) {
      replay();
      return () => {
        alive.current = false;
      };
    }
    let unsubscribe: (() => void) | null = null;
    getCase(caseId)
      .then((d) => {
        if (!alive.current) return;
        setDetail(d);
        setHead(headOf(d));
        setSteps(d.steps);
        setMode("live");
        unsubscribe = subscribeCase(
          caseId,
          (step) => {
            setSteps((prev) => (prev.some((p) => p.seq === step.seq) ? prev : [...prev, step]));
            if (shouldRefetch(step)) void refetch(caseId);
          },
          (h) => setHead(h),
          () => {
            // Stream closed by the browser (e.g. 404 after a brain restart): confirm, else replay.
            getCase(caseId).then((d2) => alive.current && setDetail(d2)).catch(replay);
          },
        );
      })
      .catch(replay);
    return () => {
      alive.current = false;
      unsubscribe?.();
    };
  }, [caseId, refetch, replay]);

  return { detail, head, steps, mode };
}
