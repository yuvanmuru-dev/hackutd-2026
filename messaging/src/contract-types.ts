/* Generated from contracts/schema.json (v0.3) by scripts/gen_types.sh. Do not edit by hand. */

/**
 * Anything that happened on the account. POST /events. Idempotent on event_id.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "Event".
 */
export type Event = {
  [k: string]: unknown;
} & {
  event_id: string;
  user_id: string;
  type:
    | "call.started"
    | "call.ended"
    | "login"
    | "otp.sent"
    | "otp.entered"
    | "pin.attempt"
    | "protection.changed"
    | "transfer_pin.requested"
    | "sim_swap.requested"
    | "portal.signals"
    | "message.forwarded"
    | "customer.reply"
    | "face.result";
  ts: string;
  source: "portal" | "voice" | "messaging" | "console" | "watcher" | "generator" | "brain";
  call_id?: string | null;
  data: {};
};

export interface TitanContractsV03 {
  [k: string]: unknown;
}
/**
 * Where a fact came from. Every Signal and claim carries one.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "Source".
 */
export interface Source {
  name: string;
  url?: string;
  /**
   * Internal record ref, e.g. events/evt_123
   */
  record?: string;
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "Error".
 */
export interface Error {
  error: string;
  detail?: string;
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "User".
 */
export interface User {
  user_id: string;
  name: string;
  persona?: string;
  face_enabled: boolean;
}
/**
 * call.started payload. Metadata only, never content. Simulated carrier signal in the demo.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "CallData".
 */
export interface CallData {
  direction: "in" | "out";
  other_number_hash: string;
  caller_name?: string | null;
  attestation: "A" | "B" | "C" | "none";
  seen_before: boolean;
  scam_label: boolean;
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "CallEndedData".
 */
export interface CallEndedData {
  duration_s: number;
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "LoginData".
 */
export interface LoginData {
  device_hash: string;
  region: string;
  new_device: boolean;
  succeeded: boolean;
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "OtpData".
 */
export interface OtpData {
  purpose: "login" | "account_change" | "transfer_pin";
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "PinAttemptData".
 */
export interface PinAttemptData {
  ok: boolean;
  channel: "portal" | "app" | "care";
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "ProtectionChangeData".
 */
export interface ProtectionChangeData {
  name: "sim_protection" | "port_out_protection" | "scam_block";
  enabled: boolean;
  via: "portal" | "app" | "care" | "titan";
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "SimSwapData".
 */
export interface SimSwapData {
  new_device_hash: string;
  channel: "portal" | "app" | "care" | "store";
}
/**
 * Derived numbers only. Never keystrokes or typed text.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "PortalSignals".
 */
export interface PortalSignals {
  session_id: string;
  page_path: string[];
  ms_per_step?: number[];
  hesitation_ms: number;
  paste_into_pin: boolean;
  tab_switches: number;
  pointer_speed?: number | null;
  typing_rhythm_distance?: number | null;
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "ForwardedMessage".
 */
export interface ForwardedMessage {
  channel: "imessage" | "sms";
  text?: string;
  image_url?: string;
  from_hash?: string;
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "CustomerReply".
 */
export interface CustomerReply {
  channel: "imessage" | "sms" | "voice" | "web";
  text: string;
  case_id?: string;
}
/**
 * Computed on the device. No images or descriptors leave it.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "FaceResult".
 */
export interface FaceResult {
  match: boolean;
  similarity: number;
  liveness: number;
  antispoof: number;
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "CallSummary".
 */
export interface CallSummary {
  call_id: string;
  caller_name: string | null;
  attestation: "A" | "B" | "C" | "none";
  seen_before: boolean;
  scam_label: boolean;
  started_at: string;
  ended_at: string | null;
  duration_s: number;
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "Timeline".
 */
export interface Timeline {
  user_id: string;
  events: Event[];
  calls: CallSummary[];
  active_call: CallSummary | null;
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "ProtectionState".
 */
export interface ProtectionState {
  user_id: string;
  protections: {
    name: "sim_protection" | "port_out_protection" | "scam_block";
    enabled: boolean;
    updated_at: string;
  }[];
  /**
   * True while an unverified call is active: turning protections off needs the pause screen (+ face check if enabled).
   */
  shield_mode: boolean;
  transfer_pin: {
    status: "none" | "held" | "active" | "revoked";
    hold_until: string | null;
  };
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "ProtectionChangeRequest".
 */
export interface ProtectionChangeRequest {
  enabled: boolean;
  via: "portal" | "titan" | "care";
  /**
   * From POST /check; required when turning a protection off
   */
  check_id?: string;
}
/**
 * Fast gate before a sensitive action. No LLM. Must answer in < 300 ms.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "CheckRequest".
 */
export interface CheckRequest {
  user_id: string;
  action: "protection_off" | "transfer_pin" | "sim_swap" | "change_email" | "change_password" | "add_line" | "login";
  protection?: "sim_protection" | "port_out_protection" | "scam_block";
  portal_signals?: PortalSignals;
  face?: FaceResult;
  customer_choice?: "on_call_help" | "doing_it_myself";
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "CheckResponse".
 */
export interface CheckResponse {
  check_id: string;
  decision: "allow" | "pause" | "hold" | "block";
  reasons: string[];
  during_call: boolean;
  call?: CallSummary | null;
  risk?: RiskScore | null;
  case_id?: string | null;
  hold_until?: string | null;
  pause_screen?: {
    title: string;
    body: string;
    help_label: string;
    continue_label: string;
  } | null;
}
/**
 * Output of ml.score() (Lane 2b) and of the Risk agent.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "RiskScore".
 */
export interface RiskScore {
  threat: "takeover" | "coached" | "scam_text" | "bot" | "legit";
  probability: number;
  calibrated: boolean;
  confidence: "low" | "medium" | "high";
  anomaly?: number | null;
  top_reasons: {
    feature: string;
    contribution: number;
    text: string;
  }[];
  model: "rules" | "ml" | "ml+rules";
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "Signal".
 */
export interface Signal {
  group: "account" | "device" | "protection" | "call" | "location" | "portal" | "face" | "message";
  name: string;
  value: number | string | boolean | null;
  baseline?: number | string | boolean | null;
  note?: string;
  source: Source;
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "Verification".
 */
export interface Verification {
  status: "verified" | "downgraded";
  claims_checked: number;
  claims_dropped: number;
  notes: string[];
}
/**
 * Safer actions may apply automatically. Looser ones always need approval and no active suspicious call.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "Action".
 */
export interface Action {
  action_id: string;
  case_id: string;
  kind:
    | "relock"
    | "hold_transfer_pin"
    | "require_step_up"
    | "reset_pin"
    | "revoke_transfer_pin"
    | "sign_out_sessions"
    | "report_number"
    | "notify_trusted_contact"
    | "send_ftc_report"
    | "release_hold";
  direction: "safer" | "looser";
  status: "proposed" | "awaiting_approval" | "approved" | "rejected" | "applied" | "failed";
  requires_approval: boolean;
  approved_via?: ("web" | "sms" | "voice") | null;
  description: string;
  created_at: string;
  applied_at?: string | null;
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "Message".
 */
export interface Message {
  message_id: string;
  case_id: string;
  channel: "imessage" | "sms" | "voice";
  direction: "in" | "out";
  kind: "heads_up" | "alert" | "question" | "summary" | "recovery_step" | "info" | "reply" | "transcript";
  text: string;
  ts: string;
}
/**
 * Sent as one iMessage with no links. Every sentence checked by the Verifier.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "IncidentSummary".
 */
export interface IncidentSummary {
  case_number: string;
  what_happened: string;
  why_we_stepped_in: string;
  confidence_text: string;
  what_we_did: string[];
  you_approved: string[];
  next_steps: string[];
  spot_it_next_time: string;
  data_we_looked_at: string[];
  replies: {
    keyword: string;
    meaning: string;
  }[];
}
/**
 * One line on the dashboard. Streamed on GET /cases/{id}/stream as `event: step`.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "StepEvent".
 */
export interface StepEvent {
  seq: number;
  case_id: string;
  run_id: string;
  ts: string;
  agent: "system" | "context" | "risk" | "verifier" | "response" | "messaging" | "voice";
  stage: "trigger" | "context" | "risk" | "verify" | "respond" | "reach" | "await" | "recover" | "summary" | "watch";
  type:
    | "plan"
    | "tool_call"
    | "tool_result"
    | "signal"
    | "score"
    | "verify"
    | "action"
    | "message"
    | "call"
    | "transcript"
    | "approval_needed"
    | "approved"
    | "summary"
    | "error"
    | "done";
  title: string;
  data: {};
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "Case".
 */
export interface Case {
  case_id: string;
  case_number: string;
  user_id: string;
  title: string;
  status: "open" | "awaiting_reply" | "recovering" | "watching" | "closed";
  threat: ("takeover" | "coached" | "scam_text" | "bot" | "legit") | null;
  confidence: ("low" | "medium" | "high") | null;
  created_at: string;
  updated_at: string;
}
/**
 * GET /cases/{id}. Everything the dashboard and the customer /case page need.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "CaseDetail".
 */
export interface CaseDetail {
  case_id: string;
  case_number: string;
  user_id: string;
  title: string;
  status: "open" | "awaiting_reply" | "recovering" | "watching" | "closed";
  threat: ("takeover" | "coached" | "scam_text" | "bot" | "legit") | null;
  confidence: ("low" | "medium" | "high") | null;
  created_at: string;
  updated_at: string;
  user: User;
  call: CallSummary | null;
  timeline: Event[];
  risk: RiskScore | null;
  signals: Signal[];
  verification: Verification | null;
  steps: StepEvent[];
  actions: Action[];
  messages: Message[];
  summary: IncidentSummary | null;
  data_used: string[];
}
/**
 * Doors -> brain POST /cases/{id}/events (transcript lines, replies, delivery receipts).
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "CaseEventRequest".
 */
export interface CaseEventRequest {
  channel: "imessage" | "sms" | "voice" | "web";
  direction: "in" | "out";
  kind: "transcript" | "reply" | "info" | "delivery";
  text: string;
  agent?: "voice" | "messaging" | "system";
}
/**
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "ApprovalRequest".
 */
export interface ApprovalRequest {
  via: "web" | "sms" | "voice";
  note?: string;
}
/**
 * Brain -> messaging POST /internal/send. Messaging resolves the phone number; text never has links.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "SendRequest".
 */
export interface SendRequest {
  case_id: string;
  user_id: string;
  channel: "imessage" | "sms";
  kind: "heads_up" | "alert" | "question" | "summary" | "recovery_step" | "info";
  text: string;
  expects_reply: boolean;
  action_id?: string | null;
}
/**
 * Brain -> voice POST /internal/call.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "CallRequest".
 */
export interface CallRequest {
  case_id: string;
  user_id: string;
  purpose: "scam_intervention" | "verify_it_was_you";
  opening_line: string;
  facts: string[];
  pending_action_ids: string[];
}
/**
 * One labeled scenario. Lane 2a writes these; Lane 2b trains and evaluates on them.
 *
 * This interface was referenced by `TitanContractsV03`'s JSON-Schema
 * via the `definition` "DatasetScenario".
 */
export interface DatasetScenario {
  scenario_id: string;
  user_id: string;
  label: "takeover" | "coached" | "scam_text" | "bot" | "recovery_scam" | "legit";
  hard_negative: boolean;
  trigger_event_id: string;
  events: Event[];
  generator: {
    seed: number;
    variant: string;
  };
}
