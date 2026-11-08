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
  // Each effect run gets its own generation; a run is current only while gen.current still equals it.
  // (A shared boolean let a cleaned-up run's late fetch pass the check and open a stream nobody closed.)
  const gen = useRef(0);

  /** Keep the newer of two heads: a slow GET must not roll the status back past a streamed `case` event. */
  const newerHead = useCallback((d: C.Case) => setHead((h) => (h && h.updated_at > d.updated_at ? h : d)), []);

  const replay = useCallback((run: number) => {
    if (gen.current !== run) return;
    setDetail(FIXTURE);
    setHead(headOf(FIXTURE));
    setSteps(FIXTURE.steps);
    setMode("replay");
  }, []);

  const refetch = useCallback(
    async (id: string, run: number) => {
      if (inFlight.current) {
        dirty.current = true;
        return;
      }
      inFlight.current = true;
      try {
        do {
          dirty.current = false;
          const d = await getCase(id);
          if (gen.current !== run) return;
          setDetail(d);
          // The stream closes on "done" before its trailing `case` event, so the head also follows refetches.
          newerHead(headOf(d));
        } while (dirty.current);
      } catch {
        /* keep the last good detail; the stream keeps going */
      } finally {
        inFlight.current = false;
      }
    },
    [newerHead],
  );

  useEffect(() => {
    const run = ++gen.current;
    const current = () => gen.current === run;
    if (!caseId) {
      replay(run);
      return () => {
        gen.current++;
      };
    }
    let unsubscribe: (() => void) | null = null;
    const seen = new Set<number>();
    getCase(caseId)
      .then((d) => {
        if (!current()) return;
        setDetail(d);
        setHead(headOf(d));
        setSteps(d.steps);
        d.steps.forEach((s) => seen.add(s.seq));
        setMode("live");
        unsubscribe = subscribeCase(
          caseId,
          (step) => {
            if (!current()) return;
            // The stream replays history on connect: only a step we have not seen can change the case.
            if (seen.has(step.seq)) return;
            seen.add(step.seq);
            setSteps((prev) => (prev.some((p) => p.seq === step.seq) ? prev : [...prev, step]));
            if (shouldRefetch(step)) void refetch(caseId, run);
          },
          (h) => current() && newerHead(h),
          () => {
            // Stream closed by the browser (e.g. 404 after a brain restart): confirm, else replay.
            getCase(caseId)
              .then((d2) => current() && setDetail(d2))
              .catch(() => replay(run));
          },
        );
        // The effect may have been cleaned up while getCase was in flight: close what we just opened.
        if (!current()) unsubscribe();
      })
      .catch(() => replay(run));
    return () => {
      // Bumping the generation is the point: it retires this run's late callbacks.
      // eslint-disable-next-line react-hooks/exhaustive-deps
      gen.current++;
      unsubscribe?.();
    };
  }, [caseId, refetch, replay, newerHead]);

  return { detail, head, steps, mode };
}
