"""Provider boundary checks; all HTTP is mocked and caches are temporary."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from packs.guard import external as ext


def response(payload, status=200):
    result = Mock(status_code=status)
    result.json.return_value = payload
    result.raise_for_status.return_value = None
    return result


class ExternalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = patch.object(ext, "CACHE_DIR", Path(self.temp.name))
        self.cache.start()
        self.addCleanup(self.cache.stop)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_every_synthetic_domain_bypasses_both_providers(self):
        entries = json.loads(ext.SYNTHETIC_REGISTRY.read_text())["entries"]
        self.assertEqual(len(entries), len({entry["domain"] for entry in entries}))
        with patch.object(ext.requests, "get") as get, patch.object(ext.requests, "post") as post:
            for entry in entries:
                with self.subTest(domain=entry["domain"]):
                    result = ext.check_message(None, f"Verify now at https://{entry['domain']}/account")
                    self.assertEqual(result["source"]["name"], ext.SYNTHETIC_SOURCE)
                    self.assertEqual(result["result"]["source"], result["source"])
                    self.assertEqual(result["result"]["domain_age_days"], entry["registered_days_ago"])
                    self.assertEqual(result["result"]["verification_status"], "synthetic")
                    self.assertIsNone(result["result"]["known_malicious"])
            get.assert_not_called()
            post.assert_not_called()

    def test_demo_scam_domains_are_all_listed(self):
        root = ext.AGENT_DIR.parent
        paths = list((root / "contracts" / "fixtures").glob("*.json"))
        paths += list((ext.POLICY_DIR.parent / "scenarios").glob("*.json"))
        for path in paths:
            value = json.loads(path.read_text())
            events = value.get("events", [value])
            for event in events:
                if event.get("type") != "message.forwarded":
                    continue
                for host, _ in ext._extract(event["data"].get("text", "")):
                    if ext._lookalike(host):
                        self.assertIsNotNone(ext._synthetic_record(host), (path.name, host))

    def test_synthetic_subdomain_and_suffix_boundary(self):
        with patch.object(ext, "_rdap") as rdap, patch.object(ext, "_urlhaus") as urlhaus:
            result = ext.check_message(None, "https://login.t-mobile-secure-help.co")
            self.assertEqual(result["result"]["domain_age_days"], 3)
            rdap.assert_not_called()
            urlhaus.assert_not_called()
        self.assertIsNone(ext._synthetic_record("t-mobile-secure-help.co.unlisted.com"))

    def test_live_rdap_urlhaus_and_cache(self):
        created = (datetime.now(timezone.utc) - timedelta(days=3, minutes=1)).isoformat()
        bootstrap = {"services": [[["com"], ["https://registry.example/rdap/"]]]}
        registration = {"events": [{"eventAction": "registration", "eventDate": created}]}
        with patch.dict(os.environ, {"URLHAUS_AUTH_KEY": "test-only-key"}), \
             patch.object(ext.requests, "get", side_effect=[response(bootstrap), response(registration)]) as get, \
             patch.object(ext.requests, "post", return_value=response({"query_status": "no_results"})) as post:
            result = ext.check_message(None, "https://unlisted-domain.com/account")
            self.assertEqual(result["result"]["domain_age_days"], 3)
            self.assertIsNone(result["result"]["known_malicious"])
            self.assertEqual(result["result"]["checks"][0]["urlhaus"]["status"], "no_report")
            self.assertEqual(post.call_args.kwargs["headers"]["Auth-Key"], "test-only-key")
            self.assertEqual(get.call_args.args[0], "https://registry.example/rdap/domain/unlisted-domain.com")
            ext.check_message(None, "https://unlisted-domain.com/account")
            self.assertEqual(get.call_count, 2)
            self.assertEqual(post.call_count, 1)
        for path in Path(self.temp.name).glob("*.json"):
            self.assertNotIn("test-only-key", path.read_text())

    def test_missing_key_and_failed_lookup_are_unverifiable(self):
        with patch.object(ext.requests, "post") as post:
            result = ext._urlhaus("unlisted-domain.com", None)
            self.assertEqual(result["status"], "unverifiable")
            self.assertIn("missing", result["note"])
            post.assert_not_called()
        with patch.dict(os.environ, {"URLHAUS_AUTH_KEY": "test-only-key"}), \
             patch.object(ext.requests, "post", return_value=response({}, 503)) as post:
            self.assertEqual(ext._urlhaus("unlisted-domain.com", None)["status"], "unverifiable")
            self.assertEqual(ext._urlhaus("unlisted-domain.com", None)["status"], "unverifiable")
            self.assertEqual(post.call_count, 1)

    def test_rdap_provider_failure_is_cached(self):
        ext._cache_set("rdap-bootstrap", "dns-v1", {
            "services": [[["com"], ["https://registry.example/rdap/"]]]})
        with patch.object(ext.requests, "get", return_value=response({}, 503)) as get:
            self.assertEqual(ext._rdap("unlisted-domain.com")["status"], "unverifiable")
            self.assertEqual(ext._rdap("unlisted-domain.com")["status"], "unverifiable")
            self.assertEqual(get.call_count, 1)

    def test_policy_fallback_and_nvidia_embedding_path(self):
        fallback = ext.policy_lookup(None, "verification code")
        self.assertEqual(fallback["result"]["status"], "local_fallback")
        self.assertTrue(fallback["result"]["matches"][0]["url"].startswith("https://"))

        def embeddings(_url, **kwargs):
            data = kwargs["json"]
            self.assertIn(data["input_type"], {"query", "passage"})
            return response({"data": [{"index": i, "embedding": [1.0, float(i + 1)]}
                                       for i, _ in enumerate(data["input"])]})

        with patch.dict(os.environ, {"NVIDIA_API_KEY": "test-only-key"}), \
             patch.object(ext.requests, "post", side_effect=embeddings) as post:
            result = ext.policy_lookup(None, "verification code")
            self.assertEqual(result["result"]["status"], "retrieved")
            self.assertEqual(post.call_count, 2)
            ext.policy_lookup(None, "verification code")
            self.assertEqual(post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
