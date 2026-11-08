"use client";

import { useEffect } from "react";
import { markStep, noteActivity, noteKeyInterval, notePointerSpeed, noteTabSwitch } from "./session";

/**
 * Watches the page for derived behavior numbers only: time per page, the longest pause,
 * leaving the tab, average pointer speed, and typing rhythm (gaps between keydowns in a text field).
 * No key values, no typed text, nothing outside the portal: the keydown handler reads only the time and
 * whether the target is a text field, never e.key / e.code or the field's value (D-006).
 */
export function useBehavior(path: string, enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;
    markStep(path);

    let lastMove: { x: number; y: number; t: number } | null = null;
    let lastActivityWrite = 0;
    const activity = () => {
      const t = performance.now();
      if (t - lastActivityWrite < 250) return; // keep storage writes cheap
      lastActivityWrite = t;
      noteActivity();
    };
    const move = (e: PointerEvent) => {
      const t = performance.now();
      if (lastMove && t - lastMove.t > 30 && t - lastMove.t < 500) {
        const d = Math.hypot(e.clientX - lastMove.x, e.clientY - lastMove.y);
        notePointerSpeed(d / (t - lastMove.t));
      }
      if (!lastMove || t - lastMove.t > 30) lastMove = { x: e.clientX, y: e.clientY, t };
      activity();
    };
    let lastKey: { el: EventTarget; t: number } | null = null;
    const key = (e: KeyboardEvent) => {
      activity();
      const el = e.target;
      if (e.repeat || !(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement)) return;
      const t = performance.now();
      // A new field or a gap over 2 s starts a new burst; the gap itself is a pause, not rhythm.
      if (lastKey && lastKey.el === el && t - lastKey.t <= 2000) noteKeyInterval(t - lastKey.t);
      lastKey = { el, t };
    };
    const visibility = () => {
      if (document.visibilityState === "hidden") noteTabSwitch();
      else noteActivity();
    };

    window.addEventListener("pointermove", move, { passive: true });
    window.addEventListener("pointerdown", activity, { passive: true });
    window.addEventListener("keydown", key);
    window.addEventListener("scroll", activity, { passive: true });
    document.addEventListener("visibilitychange", visibility);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerdown", activity);
      window.removeEventListener("keydown", key);
      window.removeEventListener("scroll", activity);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [path, enabled]);
}
