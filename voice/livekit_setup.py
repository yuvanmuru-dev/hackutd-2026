"""D-050 provisioning/checks. --probe places one short call to the allowlisted teammate."""
import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv, set_key
from livekit import api

from config import Settings, phone


async def main(mode):
    s = Settings.from_env()
    if mode == "probe":
        from livekit_calls import LiveKitCalls
        from smoke import discover_voice
        if s.conversation_missing():
            print("CONFIGURATION REQUIRED:", ", ".join(s.conversation_missing()))
            return 1
        await discover_voice(s)
        await LiveKitCalls(s).run("usr_maya")
        print("PROBE SESSION ENDED: confirm the audible greeting with the teammate; no conversation approval attempted")
        return 0
    if not all([s.livekit_url, s.livekit_key, s.livekit_secret, s.photon_project, s.photon_secret, s.photon_number]):
        raise ValueError("LiveKit/Photon provisioning configuration is incomplete")
    phone(s.photon_number)
    lk = api.LiveKitAPI(s.livekit_url, s.livekit_key, s.livekit_secret)
    try:
        trunks = await lk.sip.list_outbound_trunk(api.ListSIPOutboundTrunkRequest())
        matches = [t for t in trunks.items if t.address == "sip.spectrum.photon.codes:5061"
            and t.transport == api.SIP_TRANSPORT_TLS and s.photon_number in t.numbers
            and t.auth_username == s.photon_project]
        if len(matches) > 1:
            raise ValueError("Multiple matching Photon trunks; select the intended trunk locally")
        if not matches and mode == "provision":
            trunk = await lk.sip.create_outbound_trunk(api.CreateSIPOutboundTrunkRequest(
                trunk=api.SIPOutboundTrunkInfo(name="Titan Photon D-050",
                    address="sip.spectrum.photon.codes:5061", transport=api.SIP_TRANSPORT_TLS,
                    numbers=[s.photon_number], auth_username=s.photon_project, auth_password=s.photon_secret)))
            matches = [trunk]
            print("Created approved Photon TLS outbound trunk")
        if not matches:
            print("CONFIGURATION REQUIRED: no matching Photon TLS outbound trunk")
            return 1
        if mode == "provision":
            env = Path(__file__).with_name(".env")
            set_key(env, "LIVEKIT_SIP_OUTBOUND_TRUNK_ID", matches[0].sip_trunk_id)
            set_key(env, "VOICE_TRANSPORT", "livekit")
            print("Saved trunk ID and transport selection in voice/.env; credentials not printed")
        print("LIVEKIT CHECK PASS: authenticated; Photon TLS trunk and configured line match")
        return 0
    finally:
        await lk.aclose()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    for flag in ["check", "provision", "probe"]:
        group.add_argument("--" + flag, action="store_true")
    args = p.parse_args()
    load_dotenv(Path(__file__).with_name(".env"))
    try:
        raise SystemExit(asyncio.run(main("provision" if args.provision else "probe" if args.probe else "check")))
    except Exception as error:
        print("LIVEKIT FAILED:", type(error).__name__, "code=", getattr(error, "code", None),
            "sip_status_code=", getattr(error, "sip_status_code", None))
        # Provider failure reasons are useful for SIP setup, but can contain
        # destinations or credentials. Never print an unfiltered SDK exception.
        import re
        from dotenv import dotenv_values
        reason = str(getattr(error, "message", ""))
        for value in dotenv_values(Path(__file__).with_name(".env")).values():
            if value and len(value) >= 4:
                reason = reason.replace(value, "[configured value]")
        reason = re.sub(r"\+?\d{7,}", "[number]", reason)
        print("SANITIZED REASON:", reason[:600])
        raise SystemExit(1) from None
