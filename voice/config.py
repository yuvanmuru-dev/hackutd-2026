"""Configuration only; never print credential values or telephone numbers."""
from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from urllib.parse import urlsplit


def phone(value: str) -> str:
    """Require E.164; accept a SIP user only when it is explicitly an E.164 number."""
    if value.startswith(("sip:", "sips:")):
        value = value.split(":", 1)[1].split("@", 1)[0]
    if not re.fullmatch(r"\+[1-9]\d{7,14}", value):
        raise ValueError("Expected an E.164 teammate number")
    return value


@dataclass(frozen=True, repr=False)
class Settings:
    brain_url: str = "http://localhost:8000"
    public_url: str = ""
    account_sid: str = ""
    auth_token: str = ""
    twilio_number: str = ""
    maya_number: str = ""
    allowlist: frozenset[str] = field(default_factory=frozenset)
    hash_salt: str = ""
    caller_name: str = "T-Mobile Support"
    attestation: str = "C"
    seen_before: bool = False
    scam_label: bool = False
    probe_enabled: bool = False
    tts_provider: str = "elevenlabs"
    elevenlabs_key: str = ""
    elevenlabs_voice: str = ""
    nvidia_key: str = ""
    magpie_voice: str = ""

    @classmethod
    def from_env(cls) -> Settings:
        def enabled(name: str) -> bool:
            value = os.environ.get(name, "false").lower()
            if value not in {"true", "false"}:
                raise ValueError(f"{name} must be true or false")
            return value == "true"

        return cls(
            brain_url=os.getenv("BRAIN_URL", "http://localhost:8000").rstrip("/"),
            public_url=os.getenv("VOICE_PUBLIC_URL", "").rstrip("/"),
            account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
            auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
            twilio_number=os.getenv("TWILIO_PHONE_NUMBER", ""),
            maya_number=os.getenv("MAYA_PHONE_NUMBER", ""),
            allowlist=frozenset(phone(n.strip()) for n in os.getenv("OUTBOUND_ALLOWLIST", "").split(",") if n.strip()),
            hash_salt=os.getenv("HASH_SALT", ""),
            caller_name=os.getenv("SCAM_CALLER_NAME", "T-Mobile Support"),
            attestation=os.getenv("SCAM_ATTESTATION", "C"),
            seen_before=enabled("SCAM_SEEN_BEFORE"), scam_label=enabled("SCAM_LABEL"),
            probe_enabled=enabled("VOICE_BRIDGE_PROBE_ENABLED"),
            tts_provider=os.getenv("TTS_PROVIDER", "elevenlabs"),
            elevenlabs_key=os.getenv("ELEVENLABS_API_KEY", ""),
            elevenlabs_voice=os.getenv("ELEVENLABS_VOICE_ID", ""),
            nvidia_key=os.getenv("NVIDIA_API_KEY", ""),
            magpie_voice=os.getenv("MAGPIE_VOICE_ID", ""),
        )

    def missing(self, *, forwarding: bool = False, speech: bool = False) -> list[str]:
        required = {
            "VOICE_PUBLIC_URL": self.public_url, "TWILIO_ACCOUNT_SID": self.account_sid,
            "TWILIO_AUTH_TOKEN": self.auth_token, "OUTBOUND_ALLOWLIST": self.allowlist,
            "HASH_SALT": self.hash_salt,
        }
        if forwarding:
            required.update(TWILIO_PHONE_NUMBER=self.twilio_number, MAYA_PHONE_NUMBER=self.maya_number)
        if speech:
            if self.tts_provider == "elevenlabs":
                required.update(ELEVENLABS_API_KEY=self.elevenlabs_key, ELEVENLABS_VOICE_ID=self.elevenlabs_voice)
            elif self.tts_provider == "magpie":
                required.update(NVIDIA_API_KEY=self.nvidia_key, MAGPIE_VOICE_ID=self.magpie_voice)
            else:
                return ["TTS_PROVIDER must be elevenlabs or magpie"]
        errors = [name for name, value in required.items() if not value]
        if self.public_url:
            parts = urlsplit(self.public_url)
            if parts.scheme != "https" or not parts.netloc or parts.path or parts.query or parts.fragment or parts.username:
                errors.append("VOICE_PUBLIC_URL must be an HTTPS origin")
        if self.attestation not in {"A", "B", "C", "none"}:
            errors.append("SCAM_ATTESTATION must be A, B, C, or none")
        if forwarding and self.maya_number:
            try:
                if phone(self.maya_number) not in self.allowlist:
                    errors.append("MAYA_PHONE_NUMBER must be in OUTBOUND_ALLOWLIST")
                phone(self.twilio_number)
                if self.twilio_number == self.maya_number:
                    errors.append("Forwarding destination must differ from the Twilio number")
            except ValueError:
                errors.append("Forwarding numbers must use E.164")
        return errors
