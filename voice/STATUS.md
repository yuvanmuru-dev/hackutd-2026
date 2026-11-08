# Lane 4 checkpoint

Branch: `lane/voice`; issue #32. All edits are inside `voice/`. Main was rebased through `1983dfa` on 2026-11-07; re-read D-035, D-041, D-042 and D-046. `.env.example` is restored with names/defaults only; live values are in ignored `voice/.env`.

Implemented locally: signed allowlisted probe/forwarding routes; shared-contract brain client; local `POST /internal/call`; deduplicated teammate-only outbound Twilio calls; call-bound one-use stream grants; Pipecat input/output; hosted Nemotron ASR; streamed Lightning intent interpretation with thinking disabled; Safety Guard; redacted case transcripts; strict one-question voice approvals; interruption gating; brain 409 preservation; delivery status callbacks and graceful hangup. No scam-call audio is recorded or analyzed. The brain owns recovery texting (D-042), summary, watch and account changes.

**Not ready for live intervention approvals.** An isolated check against the actual brain recovery loop shows that incoming voice transcripts and uncorrelated voice customer.reply events can apply recovery actions. This bypasses the door's complete-question gate and can advance another step alongside its explicit approval request. Lane 1 owns the fix. Do not enable brain voice dispatch or run the real outbound call example until the integration gate passes.

## Checks actually run

Commands below run from `voice/` using its pinned environment. Windows asyncio tests/network checks require the approved execution outside the restricted socket sandbox; no test behavior or checks were weakened.

- `.venv/Scripts/python.exe -m pytest -q -o faulthandler_timeout=25`: **43 passed, 1 warning in 18.98s**. The warning is Pipecat's upstream deprecated AudioContextTTSService import. Includes the real Pipecat WebSocket/serializer/turn/output pipeline with synthetic hosted services: transcript delivery, one explicit approval after the finished question, next question, farewell and worker shutdown. Also tests actual MOCK-brain metadata forwarding and shield mode, allowlisting, signature/token binding, dedupe, redaction, Safety Guard rejection and no recording.
- `.venv/Scripts/python.exe smoke.py --offline`: both TTS factories constructed; `OFFLINE PASS: shared fixtures valid; pipecat-ai=1.15.0`.
- `.venv/Scripts/python.exe ../scripts/validate_contracts.py`: **PASS 57 fixtures/events valid**.
- `.venv/Scripts/python.exe smoke.py --conversation`: selected ElevenLabs voice discovered; **CONVERSATION PROVIDERS PASS**: synthetic speech recognized by hosted ASR, Lightning intent validated, Safety Guard passed, **37182 reply PCM bytes** synthesized. No call or audio file. A separate live Lightning SSE intent check returned `help` in **485 ms**; this is one request measurement, not phone first-word latency.
- `.venv/Scripts/python.exe scripts/check_brain_approval_boundary.py`: **exit 1**, `FAIL transcript: uncorrelated voice text approved 1 recovery action(s)` and `FAIL customer.reply: uncorrelated voice text approved 1 recovery action(s)`. Uses actual brain HTTP routes and recovery logic with only model interpretation substituted; no server/provider call or message. It also checks explicit voice approval advances just one text question once the unsafe paths are fixed. This is a required integration gate before live approvals.
- Twilio read-only owned-number lookup with the updated lane-local credentials: HTTP 200, **0 owned numbers; 0 configured voice-number matches**. No webhook was changed, number purchased or account upgraded.
- `git diff --check`: no whitespace errors. `gitleaks` is not installed; no secret scan or hook run is claimed.
- Python compilation and a whitespace scan of all candidate voice source/docs/template passed. A targeted comparison found no configured credential/phone values in those files; this does not replace gitleaks.

The rebase initially paused because the restored untracked template would be overwritten. It was preserved, the rebase finished, and the template was restored. The autostashed conversation edits were reapplied without conflicts.

## Runtime and provider status

`voice/.env` now selects `NEMOTRON_VOICE_MODEL=nvidia/nemotron-3.5-lightning-30b-a3b` and `VOICE_LLM_BASE_URL=https://integrate.api.nvidia.com/v1`. Requests send `chat_template_kwargs: {enable_thinking: false}`. The retired Nano 410/catalog 404 issue is resolved by D-035. NVIDIA ASR configuration and Safety Guard checks pass with the user's key. No secrets are printed here.

The D-046 public origin is `https://hits-shoes-predict-equipped.trycloudflare.com`; the probe is enabled in the lane-local environment. Final health checks returned HTTP 200 / ok=true for brain, local voice and public voice; both voice responses confirmed milestone=bridge, probe_enabled=true. The previously started MOCK brain (PID 57744) has no VOICE_URL/MESSAGING_URL, so it does not dispatch outbound calls/messages. The existing bridge-only voice process (PID 38300, port 8100) was intentionally not replaced with the intervention implementation while the approval boundary is unresolved. These runtime observations must be rechecked after any restart.

GitHub reports PR #42 as closed and not merged, head fa3faa4. The restored template and current conversation work are local and uncommitted; no PR was reopened, remote branch force-pushed or merge performed.

To finish the bridge test, an owned trial voice number must exist in the supplied Twilio account. Save its Voice webhook to `<VOICE_PUBLIC_URL>/webhooks/twilio/bridge-probe`, POST, then call from a verified/allowlisted teammate phone. Do not curl-POST the signed route. Greeting proves trial Stream works; an actual trial restriction/error code goes to Yuvan for an upgrade decision (D-046). Missing setup does not prove trial streaming is blocked.

Not verified: phone greeting/exchange, real Twilio signed callbacks, forwarding to a teammate phone, Photon SIP, Magpie cloud synthesis, venue connectivity, listener-perceived first words under two seconds, or safe integrated approvals on the current brain. No real call was placed and no team-chat result was sent.

## Questions sent to Lane 1

```text
QUESTION FOR LANE 1
Lane / issue / branch: 4 voice / #32 / lane/voice
Blocked on: Incoming transcript/reply text can approve recovery actions independently of the explicit voice action endpoint.
Context: server.case_event() notifies recovery for direction=in, kind=transcript; workflow.recover() interprets YES/NO and applies the next action. The voice door separately calls /actions/{id}/approve after a complete spoken question. The isolated check reproduces unsolicited approval for both transcript and customer.reply.
What the docs say: D-042 advances text prompts after voice approvals. The handoff requires every transcript plus explicit action endpoints. D-011/D-012 require bounded customer approval.
Options: A) Make transcript audit-only and prevent uncorrelated voice customer.reply from approving recovery; use explicit action endpoints for voice decisions. B) Approve a correlated voice reply contract.
My recommendation: A, preserving the existing contract shapes. Run voice/scripts/check_brain_approval_boundary.py after the fix.
Can I keep working meanwhile? yes: provider checks, local transport tests and docs are complete; live intervention approval testing is held.
```

```text
QUESTION FOR LANE 1
Lane / issue / branch: 4 voice / #32 / lane/voice
Blocked on: An owned voice number for the signed trial probe webhook.
Context: Updated credentials authenticate, but Twilio lists zero owned numbers. There is no matching number resource to update.
What the docs say: D-041 requires the trial number in this account; D-046 specifies the existing signed probe. No purchases without Yuvan.
Options: A) Claim the free trial number in this account, or provide credentials for the account owning the existing number. B) Coordinate the existing Photon/Twilio SIP route.
My recommendation: A. Update voice/.env locally; do not send keys in chat.
Can I keep working meanwhile? yes: local/provider conversation checks are complete; the actual probe needs the number.
```

## D-048 console probe update

Lane 1 clarified that the trial number is shared/Twilio-owned, so zero IncomingPhoneNumbers API results do not establish missing setup. The owned-number blocker above is superseded.

Using the signed-in Twilio One Console on 2026-11-07, opened Voice -> Try out Voice -> Receive a call -> Custom. The existing URL incorrectly ended in `/twilio/voice`. Changed it to `https://hits-shoes-predict-equipped.trycloudflare.com/webhooks/twilio/bridge-probe`, retained POST, and clicked Save. The console visibly confirmed **Webhook saved successfully**. No credentials, caller IDs, purchases or upgrades were changed. The caller selector already contains a verified teammate phone; its number is intentionally omitted here.

A read-only Python/httpx GET of local and public `/health` returned `200 bridge True` for both (milestone=bridge; probe_enabled=true). The tunnel was not restarted. Requested that the user call the trial number and report the audible outcome. The phone greeting and trial streaming capability remain unverified until that call occurs. No result was posted to team chat.

The separate incoming transcript/customer.reply approval bug remains unresolved: the Lane 1 reply supplied probe instructions rather than an approval-boundary fix. Intervention approval testing remains on hold.

## Incoming probe result: diagnostic follow-up

User reports a restriction/error announcement rather than the Titan greeting. Twilio Calls API returned HTTP 200 and shows two inbound calls at 18:53:02 and 18:53:13 CST, lasting 5 and 6 seconds, both status completed. The console Voice Logs confirms these metadata; this does not identify which announcement played. The shared trial log table exposes no diagnostic detail link. Opening the observed Debugger event-log page displayed **Upgrade your account to keep building**. Monitor Alerts API returned 401; the older account Alerts path returned 404. No error code has been recovered and no upgrade was performed. Asked the user for the exact announcement before concluding that Media Streams itself is trial-blocked. The signed probe webhook remains saved; tunnel was not restarted.

## TwiML-fetch announcement follow-up

User recalls: “We cannot reach your tree ml number, please check the url and try again.” Treating this as a possible TwiML fetch failure, not proof that trial Media Streams is blocked. Read-only checks: local/public health HTTP 200; probe GET HTTP 405 (expected POST-only endpoint); configured account/origin match the console. Linked Call Notifications resources both returned HTTP 200 with no notifications/error code.

Added metadata-only logs for rejected provider signatures/accounts (path, signature-present boolean and account-match boolean only). Restarted voice with the current lane-local environment: old bridge PID 38300 stopped; current PID 54728, port 8100, session 6851. This now runs the current conversation implementation, but brain dispatch remains unset and no outbound intervention was requested. The approval-boundary gate remains unresolved. The Cloudflare tunnel was not restarted.

Ran `.venv/Scripts/python.exe -m pytest tests/test_bridge.py -q -o faulthandler_timeout=25`: **17 passed in 3.71s**. Public health then returned HTTP 200, probe_enabled=true. Requested one more incoming phone attempt to capture whether the provider rejects the signed request. No real call was placed by the agent and no error code or trial upgrade conclusion is claimed.

## Confirmed trial bridge blockers

Latest retry reached the service at 19:00:02 CST on 2026-11-07. Sanitized log: `provider.signature_rejected`, path `/webhooks/twilio/bridge-probe`, `signature_present=false`, `account_matches=true`. Titan rejected the unsigned request with HTTP 401. Tunnel reachability is established; no signature validation was disabled.

Checked current official Twilio documentation: https://www.twilio.com/docs/usage/trials/try-out-voice#blocked-verbs explicitly lists `<Stream>`, `<Dial><Number>` and `<Dial><Sip>` as stripped/blocked during trial. Thus the observed failure is an unsigned webhook rejection, and Media Streams/forwarding also have a documented trial restriction. No numeric provider error code was exposed; none is invented.

Sent QUESTION FOR LANE 1 requesting an existing upgraded account/number or an upgrade performed by Yuvan, as required by D-046. No purchase/upgrade or security bypass was performed. Preserve the current Cloudflare tunnel for the next configured attempt. The separate brain approval-boundary issue remains unresolved.

## D-050 Route 3 checkpoint (current)

Active transport is now Photon -> LiveKit SIP -> Pipecat; no Twilio calls, forwarding or public tunnel are used for this route. User supplied LiveKit credentials and Photon line in voice/.env. LiveKit authentication passed. Normalized the supplied ten-digit US line formatting to E.164 locally without printing it. Provisioned one `Titan Photon D-050` outbound trunk: sip.spectrum.photon.codes:5061, TLS, existing Photon project ID/secret, supplied project line. Saved generated trunk ID and VOICE_TRANSPORT=livekit in ignored voice/.env. No purchases, new Photon project, inbound dispatch rule or account upgrade.

Implementation: livekit_calls.py owns the API/room/SIP lifecycle; bot.py reuses the existing conversation pipeline with a LiveKitTransport, with a separate short greeting-only probe. A room-scoped token and max_participants=2 isolate the bot/customer. The bot must join before CreateSIPParticipant; greeting waits for answer. Dialing is cancelled if the bot exits. Ring timeout=30s, call cap=180s; failures/cancellation delete the room. No recording/egress or LiveKit inference is enabled. Same brain HTTP contracts, redaction, NVIDIA intent/Safety Guard and explicit approvals.

Actual live result: THREE short greeting-only call attempts failed before answer with `SipCallError`, `failed_precondition`, SIP **503 Service Unavailable**. Last sanitized reason: unexpected status from INVITE response: sip status: 503: Service Unavailable. The bot did join the room before each attempt. No incoming audio transcription or approval was performed. Read-only DNS resolution and TLS verification for the approved Photon endpoint pass. Read-only LiveKit room listing after failures: **Remaining Titan rooms: 0**. This does not prove the phone rang, Photon caller ID appeared or phone audio worked.

Sent QUESTION FOR LANE 1: Karthik must confirm the configured Photon caller line belongs to the same D-040 project, the secret is current, and SIP voice is enabled/available, then inspect provider-side SIP logs. LiveKit's official 503 guidance points to endpoint/provider configuration. No more blind call retries. Optional inbound Photon routing remains unimplemented. D-050 fallback requires Lane 1's decision.

Current runtime: restarted `.venv/Scripts/python.exe bot.py`, PID 61292, port 8100, session 65298. Legacy Twilio probe disabled. VOICE_CONVERSATION_ENABLED=false makes /internal/call return 503 until the brain boundary is fixed; probe CLI remains available without any approvals. The prior bridge process was already gone when restart was attempted; no unrelated process was stopped.

Commands actually run:
- `uv sync --cache-dir .cache/uv`: resolved 89 packages; installed livekit 1.2.1, livekit-api 1.2.2, livekit-protocol 1.1.31, tenacity 9.2.1 and types-protobuf. Lockfile updated inside voice/.
- `.venv/Scripts/python.exe livekit_setup.py --provision`: created approved Photon TLS outbound trunk; saved trunk ID/transport selection locally; LIVEKIT CHECK PASS.
- `.venv/Scripts/python.exe livekit_setup.py --probe`: SIP 503, three attempts as described above. ElevenLabs voice discovery passed before each attempt. No successful spoken exchange claimed.
- `.venv/Scripts/python.exe -m pytest -q -o faulthandler_timeout=25`: **49 passed, 1 upstream deprecation warning in 31.59s**. New tests cover bot-before-dial ordering, allowlisting, cleanup after dial failures, cancellation if the bot dies during dialing, no Twilio/tunnel configuration requirement and the conversation interlock.
- `.venv/Scripts/python.exe ../scripts/validate_contracts.py`: **PASS 57 fixtures/events valid**.
- `.venv/Scripts/python.exe scripts/check_brain_approval_boundary.py`: still FAIL for both transcript and customer.reply (each can approve an uncorrelated action). D-050 did not resolve that separate brain issue. No brain files were edited.

Official pricing checked: https://livekit.com/pricing currently lists 1,000 included Build-plan third-party SIP minutes; 50 minutes refers to LiveKit US local inbound calling, not the Photon trunk. Photon allowances are separate. Keep tests short and confirm actual account limits. User requested no computer use; all Route 3 work used code/API/docs only.

## D-054 merged and verified

PR #60 is now merged; fetched/rebased onto origin/main **99d6eed**, preserving all uncommitted Route 3 edits. During the first rebase, old historical commits 00cad89/fa3faa4 duplicated already-applied local commits: verified matching stable patch IDs e46c4bed6fa0650f915e558a0cd3c79659ad1b49 and 36d7806ed87cafabb31bc5b8bfc53563dfd42b26, then dropped only their duplicate replays. The Route 3 autostash reapplied cleanly. No tests, hooks or checks were skipped or weakened.

Ran `.venv/Scripts/python.exe scripts/check_brain_approval_boundary.py` against the newly merged actual brain code: **PASS transcript: audit/reply did not approve; explicit voice decision advanced one text question** and **PASS customer.reply: audit/reply did not approve; explicit voice decision advanced one text question**. The earlier approval blocker is resolved by D-054. No brain files were edited by Lane 4.

Lane 1 chose option A for Photon SIP 503: Karthik checks project-owned line, current secret, line voice/SIP status and Photon logs; someone on site/event Discord asks Photon's sponsor team. Thirty-minute assisted investigation window; Yuvan selects Route 1 upgrade or text-only if unresolved. No more blind calls were attempted after that instruction. No messages were sent externally by this agent. VOICE_CONVERSATION_ENABLED remains false to prevent automated attempts while provider investigation is pending. Enable it only for a coordinated test after provider readiness is confirmed.

Final checks after rebasing PR #60: `.venv/Scripts/python.exe -m pytest -q -o faulthandler_timeout=25` -> **49 passed, 1 upstream warning in 31.06s**; `.venv/Scripts/python.exe ../scripts/validate_contracts.py` -> **PASS 57 fixtures/events valid**; `.venv/Scripts/python.exe smoke.py --offline` -> both TTS factories constructed and OFFLINE PASS. Compilation and a targeted configured-secret comparison against candidate voice source/docs/template passed (not a gitleaks scan); `git diff --check` has no whitespace errors. Changes remain local/uncommitted inside voice/. The last runtime health check found voice HTTP 200 and /internal/call interlock HTTP 503; no brain process was listening on 8000 at that check. Provider investigation, live phone audio and latency remain unverified.

## PR publication checks

Release verification: voice pytest **49 passed, 1 upstream warning in 22.39s**; D-054 integration gate **PASS** for transcript and customer.reply; contract validator **PASS 57 fixtures/events valid**. Downloaded official Gitleaks v8.30.1 into ignored voice/.cache and verified its release checksum. `gitleaks git --staged --redact --no-banner` and `gitleaks git --log-opts="origin/main..HEAD" --redact --no-banner` both report **no leaks found**. No secrets or live environment files are staged.

Known CI blocker: `python scripts/check_lane.py lane/voice origin/main` flags two existing negative-test inputs in voice/tests/test_conversation.py (unsafe opening and password-request rejection tests) as D-012 production prompts. The checks/tests were not weakened or bypassed; Lane 1 must approve a test-aware guardrail correction. Publishing as a draft with this failure explicit.

Credential clarification for sponsor support: the supplied PHOTON_SECRET_KEY is a Photon 2.0 Project API key, currently passed to SIP auth_password per the supplied setup. It is not a separately generated outbound SIP password or a Stable project secret. SIP credential compatibility remains unverified and should be checked alongside Photon-side 503 logs. No credential, project identifier or sending number is included here.

## D-057 / PR #62 integrated

Updated lane/voice from main **4b5cb3b**, including merged #62 and D-055 through D-058. `voice/.venv/Scripts/python.exe scripts/check_lane.py lane/voice origin/main` (run from repository root) now reports **PASS lane guardrails (25 files, branch lane/voice)**. The earlier negative-test guardrail blocker is resolved by Lane 1's D-057 change; no test was changed or weakened here. Gitleaks branch-history scan again reports no leaks found.

PR #61 remains a draft until a real call rings. No Photon calls were retried. D-055 now records the provider root cause: the shared line is not voice eligible, and outbound voice needs separately generated SIP credentials rather than the project API key. Waiting for Karthik's eligible line/SIP credentials (sponsor ticket #1916); any paid fallback remains Yuvan's decision. Current environment and provisioning code have not been repointed to an unverified replacement credential.

Post-update validation: voice pytest **49 passed, 1 upstream warning in 34.87s**; D-054 gate **PASS** for both cases; shared contracts **PASS 57 fixtures/events valid**.

## Photon support correction: real ring and audible greeting confirmed

User supplied generated outbound SIP credentials and confirmed the Default profile was enabled with SHA-256 selected. Saved those credentials only in ignored voice/.env as PHOTON_SIP_USERNAME/PHOTON_SIP_PASSWORD. Replaced the old shared caller ID with the user-supplied voice-enabled line (normalized US formatting to E.164 locally). Inbound calling remained unchanged/disabled; no computer control, purchases or account upgrades were performed.

Updated the EXISTING configured LiveKit outbound trunk in place to **sip.photon.codes:5061**, TLS, the replacement caller ID and generated SIP username/password. Project API credentials are no longer used for SIP; known API-key values are rejected. The provisioning/check command confirmed the corrected endpoint, TLS, caller line and SIP username. No credential values, project identifier or phone number are recorded here.

Actual test results: the first specifically authorized greeting-only probe completed without SIP error; the user confirmed the phone rang but was not answered. The user explicitly requested another attempt. The second probe completed without SIP error, and the user confirmed **Yes, I heard the greeting** after answering. Thus Photon -> LiveKit SIP -> Pipecat -> ElevenLabs phone output is verified. No incoming audio was processed or recorded by these greeting-only probes; they did not attempt recovery approvals. No further calls were placed. Listener-perceived first-word latency, live ASR, conversation turns, case transcripts from a live conversation and spoken approvals remain unverified.

Validation: `.venv/Scripts/python.exe -m pytest -q -o faulthandler_timeout=25` -> **51 passed, 1 upstream deprecation warning in 21.98s**; D-054 approval-boundary gate -> both cases PASS; shared contract validator -> PASS 57 fixtures/events valid. New regression tests prove the configured trunk is updated with dedicated SIP credentials rather than creating a replacement, and project API keys are rejected as SIP passwords. Existing allowlist/TLS/call-cleanup checks are retained.

The condition to keep PR #61 draft until a real call rings is now satisfied. Report only the verified bridge result; do not claim the entire Lane 4 definition of done or close #32 until the live conversation/approval milestone is tested. VOICE_CONVERSATION_ENABLED remains false; no automated intervention retry was enabled.
