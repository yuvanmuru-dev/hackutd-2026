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
