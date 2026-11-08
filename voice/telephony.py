"""Only the configured, allowlisted teammate can receive intervention calls."""
from __future__ import annotations

from urllib.parse import quote
import xml.etree.ElementTree as ET

import httpx

from config import Settings, phone


def stream_twiml(origin: str, token: str) -> str:
    root = ET.Element("Response")
    stream = ET.SubElement(ET.SubElement(root, "Connect"), "Stream",
        url=origin.replace("https://", "wss://", 1) + "/ws/bridge")
    ET.SubElement(stream, "Parameter", name="bridge_token", value=token)
    return ET.tostring(root, encoding="unicode")


class TwilioCalls:
    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client = client
        self.settings = settings

    async def place(self, user_id: str, token: str) -> str:
        s = self.settings
        if user_id != "usr_maya" or phone(s.maya_number) not in s.allowlist:
            raise ValueError("No allowlisted teammate mapping for this user")
        path = "https://api.twilio.com/2010-04-01/Accounts/" + quote(s.account_sid, safe="") + "/Calls.json"
        response = await self.client.post(path, auth=(s.account_sid, s.auth_token), data={
            "To": s.maya_number, "From": s.twilio_number,
            "Twiml": stream_twiml(s.public_url, token), "Record": "false", "Timeout": "30",
            "StatusCallback": s.public_url + "/webhooks/twilio/intervention-status?request=" + quote(token, safe=""),
            "StatusCallbackMethod": "POST", "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"],
        })
        response.raise_for_status()
        sid = response.json().get("sid")
        if not isinstance(sid, str) or not sid.startswith("CA"):
            raise ValueError("Provider did not return a call ID")
        return sid
