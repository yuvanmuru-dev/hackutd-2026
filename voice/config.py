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
    llm_base_url: str = "https://integrate.api.nvidia.com/v1"
    llm_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    nano_base_url: str = ""
    nano_model: str = ""
    nano_key: str = ""
    guard_model: str = "nvidia/llama-3.1-nemotron-safety-guard-8b-v3"
    voice_transport: str = "livekit"
    conversation_enabled: bool = False
    livekit_url: str = ""
    livekit_key: str = ""
    livekit_secret: str = ""
    livekit_trunk: str = ""
    photon_number: str = ""
    photon_project: str = ""
    photon_secret: str = ""
    photon_sip_username: str = ""
    photon_sip_password: str = ""

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
            llm_base_url=os.getenv("VOICE_LLM_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/"),
            llm_model=os.getenv("NEMOTRON_VOICE_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b"),
            nano_base_url=os.getenv("NEMOTRON_NANO_BASE_URL", "").rstrip("/"),
            nano_model=os.getenv("NEMOTRON_NANO_SELF_MODEL", ""),
            nano_key=os.getenv("NEMOTRON_NANO_SELF_KEY", ""),
            guard_model=os.getenv("VOICE_GUARD_MODEL", "nvidia/llama-3.1-nemotron-safety-guard-8b-v3"),
            voice_transport=os.getenv("VOICE_TRANSPORT", "livekit"),
            conversation_enabled=enabled("VOICE_CONVERSATION_ENABLED"),
            livekit_url=os.getenv("LIVEKIT_URL", ""),
            livekit_key=os.getenv("LIVEKIT_API_KEY", ""),
            livekit_secret=os.getenv("LIVEKIT_API_SECRET", ""),
            livekit_trunk=os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID", ""),
            photon_number=os.getenv("PHOTON_PHONE_NUMBER", ""),
            photon_project=os.getenv("PHOTON_PROJECT_ID", ""),
            photon_secret=os.getenv("PHOTON_SECRET_KEY", ""),
            photon_sip_username=os.getenv("PHOTON_SIP_USERNAME", ""),
            photon_sip_password=os.getenv("PHOTON_SIP_PASSWORD", ""),
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

    def conversation_missing(self) -> list[str]:
        if self.voice_transport == "livekit":
            required = {"LIVEKIT_URL": self.livekit_url, "LIVEKIT_API_KEY": self.livekit_key,
                "LIVEKIT_API_SECRET": self.livekit_secret, "LIVEKIT_SIP_OUTBOUND_TRUNK_ID": self.livekit_trunk,
                "PHOTON_PHONE_NUMBER": self.photon_number, "PHOTON_SIP_USERNAME": self.photon_sip_username,
                "PHOTON_SIP_PASSWORD": self.photon_sip_password, "MAYA_PHONE_NUMBER": self.maya_number,
                "OUTBOUND_ALLOWLIST": self.allowlist, "HASH_SALT": self.hash_salt}
            if self.tts_provider == "elevenlabs":
                required.update(ELEVENLABS_API_KEY=self.elevenlabs_key, ELEVENLABS_VOICE_ID=self.elevenlabs_voice)
            elif self.tts_provider == "magpie":
                required.update(MAGPIE_VOICE_ID=self.magpie_voice)
            errors = [name for name, value in required.items() if not value]
            if self.photon_sip_password.startswith(("pho_sk_", "pho_ask_")) or (
                    self.photon_sip_password and self.photon_sip_password == self.photon_secret):
                errors.append("PHOTON_SIP_PASSWORD must be the generated outbound SIP password, not an API key")
            if self.tts_provider not in {"elevenlabs", "magpie"}:
                errors.append("TTS_PROVIDER must be elevenlabs or magpie")
            origin = urlsplit(self.livekit_url)
            if origin.scheme != "wss" or not origin.hostname or origin.username or origin.query or origin.fragment or origin.path not in {"", "/"}:
                errors.append("LIVEKIT_URL must be a WSS origin")
            try:
                if phone(self.maya_number) not in self.allowlist:
                    errors.append("MAYA_PHONE_NUMBER must be in OUTBOUND_ALLOWLIST")
                if phone(self.photon_number) == self.maya_number:
                    errors.append("Photon line must differ from the teammate destination")
            except ValueError:
                errors.append("Photon and teammate numbers must use E.164")
        else:
            errors = self.missing(forwarding=True, speech=True)
            if self.voice_transport != "twilio":
                errors.append("VOICE_TRANSPORT must be livekit or twilio")
        if not self.nvidia_key:
            errors.append("NVIDIA_API_KEY")
        if not self.llm_model:
            errors.append("NEMOTRON_VOICE_MODEL (working NVIDIA Nemotron served ID)")
        target = urlsplit(self.llm_base_url)
        if (target.scheme not in {"http", "https"} or not target.hostname or target.username
                or target.query or target.fragment
                or (target.scheme == "http" and target.hostname not in {"localhost", "127.0.0.1", "::1"})):
            errors.append("VOICE_LLM_BASE_URL must be HTTPS or a local NVIDIA endpoint")
        if target.hostname == "integrate.api.nvidia.com" and self.llm_model and not self.llm_model.startswith("nvidia/"):
            errors.append("NEMOTRON_VOICE_MODEL must be an NVIDIA model")
        if not self.guard_model.startswith("nvidia/"):
            errors.append("VOICE_GUARD_MODEL must be an NVIDIA model")
        return errors
