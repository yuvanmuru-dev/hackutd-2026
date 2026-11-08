"""Bounded LiveKit provider diagnostics, without credentials or phone numbers."""
import json
import re
from urllib.parse import quote


def provider_diagnostics(error, settings):
    # Model, HTTP and speech errors can contain customer text. Only LiveKit's
    # structured server error is eligible for provider message/metadata logging.
    try:
        from livekit.api.twirp_client import ServerError
    except ImportError:  # Older SDKs use TwirpError for the same structured failures.
        from livekit.api.twirp_client import TwirpError as ServerError
    if not isinstance(error, ServerError):
        return {}
    fields = ("account_sid", "auth_token", "elevenlabs_key", "nvidia_key",
              "livekit_key", "livekit_secret", "nano_key", "photon_project", "photon_secret",
              "photon_sip_username", "photon_sip_password", "maya_number",
              "photon_number", "twilio_number", "hash_salt")
    private = {str(getattr(settings, field, "")) for field in fields}
    private.update(getattr(settings, "allowlist", ()))
    private = {part for value in private if len(value) >= 4
               for part in (value, quote(value, safe=""))}
    sensitive_key = re.compile(
        r"password|secret|token|authorization|credential|api.?key|username|"
        r"phone|number|(?:^|_)(?:from|to|uri|headers|body|text|transcript|content)(?:$|_)", re.I)

    def clean_text(value):
        for secret in sorted(private, key=len, reverse=True):
            value = value.replace(secret, "[redacted]")
        value = re.sub(r"(?im)\b(?:proxy-)?authorization\s*:[^\r\n]*", "[redacted authorization]", value)
        value = re.sub(r"(?i)\b(?:https?|wss?|sips?)://?[^\s<>\"']+", "[redacted URI]", value)
        value = re.sub(r"(?i)\bsips?:[^\s<>\"']+", "[redacted URI]", value)
        value = re.sub(r"(?i)\b(?:password|secret|token|api[_-]?key)\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
                       "[redacted credential]", value)
        value = re.sub(r"(?<!\w)\+?\d[\d(). -]{6,}\d\b", "[redacted number]", value)
        return value[:2048]

    def clean(value, depth=0):
        if depth > 4:
            return "[depth limit]"
        if isinstance(value, dict):
            return {clean_text(str(k))[:128]: "[redacted]" if sensitive_key.search(str(k)) else clean(v, depth+1)
                    for k, v in list(value.items())[:32]}
        if isinstance(value, (list, tuple)):
            return [clean(v, depth+1) for v in value[:16]]
        if isinstance(value, str):
            # error_details may itself be JSON; sanitize its field names too.
            if value.lstrip().startswith(("{", "[")) and len(value) <= 16384:
                try:
                    return clean(json.loads(value), depth+1)
                except (ValueError, RecursionError):
                    pass
            return clean_text(value)
        if value is None or isinstance(value, (bool, int, float)):
            return value
        return "[unsupported value]"

    sip_status = getattr(error, "sip_status_code", None) or error.metadata.get("sip_status_code")
    try:
        sip_status = int(sip_status)
    except (TypeError, ValueError):
        sip_status = None
    if sip_status is not None and not 100 <= sip_status <= 699:
        sip_status = None
    return {"sip_status_code": sip_status,
            "provider_code": clean_text(error.code),
            "provider_http_status": error.status,
            "provider_message": clean_text(error.message),
            "provider_metadata": clean(error.metadata)}
