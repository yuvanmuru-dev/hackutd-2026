"""Provider reasons remain useful without retaining secrets or customer data."""
import json
from dataclasses import replace

try:
    from livekit.api.twirp_client import SipCallError
except ImportError:
    from livekit.api.twirp_client import TwirpError as SipCallError

from diagnostics import provider_diagnostics
from test_bridge import SETTINGS


def test_sip_reason_and_support_ids_survive_but_private_fields_do_not():
    settings = replace(SETTINGS, photon_sip_password="synthetic-private-password",
        livekit_secret="synthetic-livekit-secret", maya_number="+12025550123")
    error = SipCallError("permission_denied",
        "unexpected status from INVITE response: sip status: 403: Forbidden; "
        "destination +1 (202) 555-0123; synthetic-private-password; "
        "https://example.invalid/?token=unknown-value", status=403,
        metadata={"sip_status_code": "403", "sip_status": "Forbidden",
            "call_id": "SCL_synthetic", "auth_password": "unknown-private-password",
            "error_details": json.dumps({"reason": "provider rejected INVITE",
                "token": "unknown-nested-token", "to_uri": "sip:+12025550123@example.invalid"}),
            "headers": {"Authorization": "Digest unknown-header-secret"}})
    result = provider_diagnostics(error, settings)
    logged = json.dumps(result)
    assert result["provider_metadata"]["sip_status_code"] == "403"
    assert result["sip_status_code"] == 403
    assert result["provider_metadata"]["sip_status"] == "Forbidden"
    assert result["provider_metadata"]["call_id"] == "SCL_synthetic"
    assert "provider rejected INVITE" in logged
    assert "403: Forbidden" in result["provider_message"]
    for private in ("synthetic-private-password", "unknown-value", "unknown-private-password",
                    "unknown-nested-token", "unknown-header-secret", "555-0123", "12025550123"):
        assert private not in logged


def test_unstructured_customer_or_model_exception_is_not_logged():
    assert provider_diagnostics(ValueError("private customer utterance"), SETTINGS) == {}


def test_nested_metadata_is_bounded_and_unknown_values_are_not_stringified():
    error = SipCallError("unavailable", "Forbidden", status=503,
        metadata={"items": list(range(100)), "nested": {"a": {"b": {"c": {"d": "x"}}}},
                  "object": object(), "long": "x" * 10000})
    result = provider_diagnostics(error, SETTINGS)["provider_metadata"]
    assert len(result["items"]) == 16
    assert len(result["long"]) == 2048
    assert "depth limit" in json.dumps(result)
    assert result["object"] == "[unsupported value]"


def test_intervention_failure_emits_redacted_sdk_message_and_metadata(caplog):
    import logging
    import time
    from unittest.mock import AsyncMock
    from fastapi.testclient import TestClient
    from service import create_app
    from test_conversation import ModelStub, setup_case
    from test_livekit_calls import LK

    _, request, brain = setup_case()
    provider = AsyncMock()
    provider.run.side_effect = SipCallError("permission_denied",
        "INVITE response 403 Forbidden " + LK.photon_sip_password, status=403,
        metadata={"sip_status_code": "403", "sip_status": "Forbidden"})
    caplog.set_level(logging.INFO, logger="titan.voice")
    with TestClient(create_app(replace(LK, conversation_enabled=True), brain,
            call_provider=provider, model_provider=ModelStub(), asr_check=AsyncMock()),
            client=("127.0.0.1", 50000)) as client:
        assert client.post("/internal/call", json=request).status_code == 202
        for _ in range(50):
            events = [json.loads(r.message) for r in caplog.records if r.name == "titan.voice"]
            failure = next((e for e in events if e["event"] == "intervention.setup_failed"), None)
            if failure: break
            time.sleep(.01)
        assert failure is not None
        assert failure["sip_status_code"] == 403
        assert failure["provider_metadata"]["sip_status"] == "Forbidden"
        assert "INVITE response 403 Forbidden" in failure["provider_message"]
        assert LK.photon_sip_password not in json.dumps(failure)


def test_model_setup_failure_is_logged_and_audited_without_dialing(caplog):
    import logging
    import time
    from unittest.mock import AsyncMock
    from fastapi.testclient import TestClient
    from service import create_app
    from test_conversation import ModelStub, setup_case
    from test_livekit_calls import LK

    _, request, brain = setup_case()
    model = ModelStub()
    model.verify = AsyncMock(side_effect=ValueError("synthetic private model output"))
    provider = AsyncMock()
    caplog.set_level(logging.INFO, logger="titan.voice")
    with TestClient(create_app(replace(LK, conversation_enabled=True), brain,
            call_provider=provider, model_provider=model, asr_check=AsyncMock()),
            client=("127.0.0.1", 50000)) as client:
        assert client.post("/internal/call", json=request).status_code == 202
        for _ in range(50):
            if brain.delivery.await_count:
                break
            time.sleep(.01)
        brain.delivery.assert_awaited_once_with(request["case_id"],
            "Titan voice setup failed; no successful conversation was confirmed.")
        provider.run.assert_not_awaited()
    events = [json.loads(r.message) for r in caplog.records if r.name == "titan.voice"]
    failure = next(e for e in events if e["event"] == "intervention.setup_failed")
    assert failure["exception_type"] == "ValueError"
    assert "synthetic private model output" not in json.dumps(events)
