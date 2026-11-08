// Console event payloads, copied from contracts/fixtures/ (event.call_started.json,
// event.t1_new_device_login.json). event_id, ts and call ids are fresh per click.
import { MAYA, newEventId, nowIso, type Contract as C } from "@/lib/api/client";

const rid = () => crypto.randomUUID().replace(/-/g, "").slice(0, 8);

export function callStarted(): C.Event {
  return {
    event_id: newEventId(),
    user_id: MAYA,
    type: "call.started",
    ts: nowIso(),
    source: "console",
    call_id: `call_${rid()}`,
    data: {
      direction: "in",
      other_number_hash: "h_8f2c19",
      caller_name: "T-Mobile Support",
      attestation: "C",
      seen_before: false,
      scam_label: false,
    },
  };
}

export function callEnded(callId: string, startedAt: string): C.Event {
  return {
    event_id: newEventId(),
    user_id: MAYA,
    type: "call.ended",
    ts: nowIso(),
    source: "console",
    call_id: callId,
    data: { duration_s: Math.max(0, Math.round((Date.now() - Date.parse(startedAt)) / 1000)) },
  };
}

export function newDeviceLogin(): C.Event {
  return {
    event_id: newEventId(),
    user_id: MAYA,
    type: "login",
    ts: nowIso(),
    source: "console",
    call_id: null,
    data: { device_hash: "h_unknown_win11", region: "Lagos, NG", new_device: true, succeeded: true },
  };
}
