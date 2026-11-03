"""Transport evidence tests; all provider traffic is fake and no code executes."""
import hashlib
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import direct_transport as transport


PROPOSAL = {"diagnosis": "A proposal only; tests have not run.",
            "patch": "--- a/convert_response.py\n+++ b/convert_response.py\n@@ -1 +1 @@\n-old\n+new\n",
            "risks": ["Excerpt-level proposal"], "tests_to_run": ["Frozen checks in a sandbox"]}


def response(**changes):
    doc = {"id": "chatcmpl-test-1", "model": transport.MODEL,
           "choices": [{"index": 0, "finish_reason": "stop", "message": {
               "role": "assistant", "content": json.dumps(PROPOSAL)}}],
           "usage": {"prompt_tokens": 42, "completion_tokens": 20, "total_tokens": 62,
                     "completion_tokens_details": {"reasoning_tokens": 10},
                     "prompt_tokens_details": {"cached_tokens": 3}, "private": "never export"},
           "private_provider_field": "not public"}
    doc.update(changes)
    return json.dumps(doc).encode()


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="source-transport-test-")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        paths = ["source-repair/trial/PROTOCOL.json", "source-repair/trial/run_trial.py",
                 "source-repair/trial/metamorphic.py", "source-repair/trial/PROTECTED_SHA256.json",
                 "source-repair/trial/direct_transport.py", "docs/META_SOURCE_REPAIR_SPEC.md"]
        paths += ["source-repair/upstream/" + n for n in transport.SOURCE_NAMES]
        for relative in paths:
            destination = self.repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(transport.ROOT / relative, destination)
        self.attempt = self.repo / "source-repair/trial/direct_meta_01"

    def reserve(self):
        return transport.reserve_attempt(self.attempt, self.repo)

    def authorize(self, **changes):
        manifest = json.loads((self.attempt / "manifest.json").read_bytes())
        auth = {"schema_version": 1, "scope": transport.AUTH_SCOPE,
                "request_sha256": manifest["request_sha256"],
                "owner_accepts_bounded_cost_risk": True,
                "authorized_utc": "2026-11-03T00:00:00+00:00"}
        auth.update(changes)
        (self.attempt / "billing_authorization.json").write_text(json.dumps(auth) + "\n")

    def send_fake(self, raw=None, status=200, headers=None):
        self.authorize()
        with patch.dict(os.environ, {"MODEL_API_KEY": "unit-test-secret-do-not-export"}, clear=True), \
             patch.object(transport, "_exchange", return_value=(status, headers or {"x-request-id": "req-test"}, raw or response())) as exchange:
            result = transport.send_reserved(self.attempt, self.repo)
        self.assertEqual(exchange.call_count, 1)
        return result

    def test_request_is_deterministic_public_and_exactly_configured(self):
        first = transport.request_bytes(self.repo)
        self.assertEqual(first, transport.request_bytes(self.repo))
        body = json.loads(first)
        self.assertEqual(body["model"], "muse-spark-1.3")
        self.assertEqual(body["n"], 1)
        self.assertEqual(body["reasoning_effort"], "medium")
        self.assertEqual(body["max_completion_tokens"], 8192)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["tools"], [])
        self.assertIs(body["stream"], False)
        self.assertIs(body["store"], False)
        prompt = body["messages"][1]["content"]
        self.assertIn(transport.UPSTREAM_REVISION, prompt)
        protocol = json.loads((self.repo / "source-repair/trial/PROTOCOL.json").read_bytes())
        for invariant in protocol["rubric"]["invariants"]:
            self.assertIn(invariant, prompt)
        for case in protocol["cases"]:
            self.assertIn(case["id"], prompt)
        self.assertNotIn("MODEL_PATCH.diff", prompt)
        self.assertNotIn("model_attempt_01", prompt)

    def test_source_mutation_blocks_preparation(self):
        (self.repo / "source-repair/upstream/convert_response.py").write_text("changed")
        with self.assertRaisesRegex(transport.TransportDenied, "frozen_input_mismatch"):
            self.reserve()
        self.assertFalse(self.attempt.exists())

    def test_exclusive_fsynced_reservation_keeps_exact_bytes(self):
        with patch.object(transport.os, "fsync", wraps=os.fsync) as fsync:
            manifest = self.reserve()
        self.assertGreaterEqual(fsync.call_count, 6)
        raw = (self.attempt / "request.json").read_bytes()
        self.assertEqual(raw, transport.request_bytes(self.repo))
        self.assertEqual(manifest["request_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(manifest["upstream_revision"], transport.UPSTREAM_REVISION)
        with self.assertRaises(FileExistsError):
            self.reserve()
        self.assertEqual((self.attempt / "request.json").read_bytes(), raw)

    def test_missing_credentials_and_billing_deny_without_transport(self):
        self.reserve()
        with patch.dict(os.environ, {}, clear=True), patch.object(transport, "_exchange") as exchange:
            blockers = transport.prerequisite_blockers(self.attempt)
            self.assertEqual(len(blockers), 2)
            with self.assertRaises(transport.TransportDenied):
                transport.send_reserved(self.attempt, self.repo)
        exchange.assert_not_called()
        events = (self.attempt / "events.jsonl").read_text()
        self.assertIn('"network_attempted":false', events)
        self.assertNotIn('"network_attempted":true', events)

    def test_credit_flag_or_assertion_does_not_enable_transport(self):
        self.reserve()
        with patch.dict(os.environ, {"MODEL_API_KEY": "fake-key", "CREDITS_CONFIRMED": "true",
                                     "PAID_OVERAGE_DISABLED": "true"}, clear=True), \
             patch.object(transport, "_exchange") as exchange:
            self.assertEqual(len(transport.prerequisite_blockers(self.attempt)), 1)
            with self.assertRaises(transport.TransportDenied):
                transport.send_reserved(self.attempt, self.repo)
        exchange.assert_not_called()

    def test_provider_offers_no_enforceable_cap(self):
        self.assertFalse(transport._verify_provider_credit_protection())

    def test_valid_owner_authorization_clears_billing_blocker(self):
        self.reserve()
        with patch.dict(os.environ, {"MODEL_API_KEY": "fake-key"}, clear=True):
            self.assertEqual(len(transport.prerequisite_blockers(self.attempt)), 1)
            self.authorize()
            self.assertEqual(transport.prerequisite_blockers(self.attempt), [])

    def test_wrong_request_mismatched_or_symlinked_authorization_denied(self):
        self.reserve()
        self.authorize()
        manifest = json.loads((self.attempt / "manifest.json").read_bytes())
        self.assertTrue(transport._verify_owner_billing_authorization(self.attempt))
        for bad in ({"request_sha256": "0" * 64},
                    {"scope": "some other scope"},
                    {"owner_accepts_bounded_cost_risk": False},
                    {"schema_version": 2},
                    {"authorized_utc": "x" * 65},
                    {"extra_field": True}):
            self.authorize(**bad)
            self.assertFalse(transport._verify_owner_billing_authorization(self.attempt), bad)
        self.assertEqual(manifest["request_sha256"],
                         json.loads((self.attempt / "manifest.json").read_bytes())["request_sha256"])
        target = self.attempt / "billing_authorization.json"
        target.unlink()
        link_source = self.attempt / "auth_source.json"
        link_source.write_text("{}")
        target.symlink_to(link_source)
        self.assertFalse(transport._verify_owner_billing_authorization(self.attempt))

    def test_denied_send_claim_cannot_be_reused(self):
        self.reserve()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(transport.TransportDenied):
                transport.send_reserved(self.attempt, self.repo)
        self.authorize()
        with patch.dict(os.environ, {"MODEL_API_KEY": "fake-key"}, clear=True), \
             patch.object(transport, "_exchange") as exchange:
            with self.assertRaises(FileExistsError):
                transport.send_reserved(self.attempt, self.repo)
        exchange.assert_not_called()

    def test_request_tampering_after_reservation_denied(self):
        self.reserve()
        (self.attempt / "request.json").write_bytes(b'{"changed":true}')
        self.authorize()
        with patch.dict(os.environ, {"MODEL_API_KEY": "fake-key"}, clear=True), \
             patch.object(transport, "_exchange") as exchange:
            with self.assertRaisesRegex(transport.TransportDenied, "request_mismatch"):
                transport.send_reserved(self.attempt, self.repo)
        exchange.assert_not_called()

    def test_uncertain_transport_keeps_partial_bytes_and_blocks_resend(self):
        self.reserve()
        self.authorize()
        partial = b'{"partial":"unit-test-secret-do-not-export"'
        with patch.dict(os.environ, {"MODEL_API_KEY": "unit-test-secret-do-not-export"}, clear=True), \
             patch.object(transport, "_exchange", side_effect=transport.TransportUncertain(partial)) as exchange:
            summary = transport.send_reserved(self.attempt, self.repo)
            self.assertEqual(summary["status"], "uncertain")
            with self.assertRaises(FileExistsError):
                transport.send_reserved(self.attempt, self.repo)
        self.assertEqual(exchange.call_count, 1)
        self.assertEqual((self.attempt.parent / ".private/direct_meta_01/response.bin").read_bytes(), partial)
        self.assertNotIn("unit-test-secret-do-not-export", (self.attempt / "events.jsonl").read_text())

    def test_valid_response_preserves_private_bytes_and_nested_usage(self):
        self.reserve()
        raw = response()
        summary = self.send_fake(raw)
        self.assertEqual(summary["status"], "response_validated_unexecuted")
        self.assertEqual(summary["usage"]["completion_tokens_details"], {"reasoning_tokens": 10})
        self.assertEqual(summary["usage"]["prompt_tokens_details"], {"cached_tokens": 3})
        self.assertNotIn("private", summary["usage"])
        private = self.attempt.parent / ".private/direct_meta_01"
        self.assertEqual((private / "response.bin").read_bytes(), raw)
        self.assertEqual((private / "MODEL_PATCH.diff").read_text(), PROPOSAL["patch"])
        self.assertEqual(summary["patch_sha256"], hashlib.sha256(PROPOSAL["patch"].encode()).hexdigest())
        self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((private / "response.bin").stat().st_mode), 0o600)
        public = (self.attempt / "transport.json").read_text()
        for private_value in ["unit-test-secret-do-not-export", "not public", "never export", PROPOSAL["diagnosis"]]:
            self.assertNotIn(private_value, public)

    def test_malformed_response_preserved_without_retry(self):
        self.reserve()
        raw = b'{"model":'
        summary = self.send_fake(raw)
        self.assertEqual(summary["error"], "malformed_json")
        self.assertEqual(summary["status"], "rejected")
        self.assertEqual((self.attempt.parent / ".private/direct_meta_01/response.bin").read_bytes(), raw)

    def test_truncated_completion_rejected(self):
        choices = json.loads(response())["choices"]
        choices[0]["finish_reason"] = "length"
        with self.assertRaisesRegex(transport.ResponseRejected, "truncated_or_nonstop"):
            transport.parse_provider_response(response(choices=choices))

    def test_identity_mismatch_rejected(self):
        with self.assertRaisesRegex(transport.ResponseRejected, "model_identity_mismatch"):
            transport.parse_provider_response(response(model="some-other-model"))

    def test_reflected_secret_never_enters_public_metadata(self):
        self.reserve()
        secret = "unit-test-secret-do-not-export"
        raw = response(id=secret, private_provider_field=secret)
        summary = self.send_fake(raw, headers={"x-request-id": secret, "set-cookie": secret})
        self.assertEqual(summary["error"], "secret_reflection")
        self.assertIsNone(summary["response_id"])
        self.assertIsNone(summary["provider_request_id"])
        self.assertNotIn(secret, (self.attempt / "transport.json").read_text())
        self.assertNotIn(secret, (self.attempt / "events.jsonl").read_text())

    def test_escaped_secret_is_also_rejected(self):
        secret = "unit-test-secret-do-not-export"
        proposal = {**PROPOSAL, "diagnosis": secret}
        raw = response(choices=[{"finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps(proposal)}}])
        escaped = raw.replace(secret.encode(), ("\\u%04x" % ord(secret[0]) + secret[1:]).encode())
        self.assertNotIn(secret.encode(), escaped)
        with self.assertRaisesRegex(transport.ResponseRejected, "secret_reflection"):
            transport.parse_provider_response(escaped, (secret,))

    def test_redirect_is_retained_and_not_followed(self):
        self.reserve()
        summary = self.send_fake(b'{"redirect":"ignored"}', status=302,
                                 headers={"Location": "https://another.example/"})
        self.assertEqual(summary["http_status"], 302)
        self.assertEqual(summary["error"], "http_error_or_redirect_no_retry")
        self.assertNotIn("Location", summary)

    def test_duplicate_keys_and_nonfinite_json_rejected(self):
        raw = response().replace(b'"model": "muse-spark-1.3"', b'"model":"wrong","model":"muse-spark-1.3"')
        with self.assertRaisesRegex(transport.ResponseRejected, "malformed_json"):
            transport.parse_provider_response(raw)
        with self.assertRaisesRegex(transport.ResponseRejected, "malformed_json"):
            transport.parse_provider_response(response().replace(b'"prompt_tokens": 42', b'"prompt_tokens": NaN'))

    def test_transport_uses_one_direct_tls_connection_and_no_redirect(self):
        connection = MagicMock()
        reply = MagicMock()
        reply.status = 302
        reply.read.side_effect = [b"redirect", b""]
        reply.getheaders.return_value = [("Location", "https://another.example/")]
        reply.getheader.return_value = None
        connection.getresponse.return_value = reply
        with patch.object(transport.http.client, "HTTPSConnection", return_value=connection) as factory:
            status, headers, raw = transport._exchange(b"{}", "fake-key")
        self.assertEqual(factory.call_count, 1)
        self.assertEqual(connection.request.call_count, 1)
        self.assertEqual(status, 302)
        self.assertEqual(raw, b"redirect")
        self.assertEqual(factory.call_args.args[0], "api.meta.ai")
        self.assertEqual(connection.request.call_args.args[:2], ("POST", "/v1/chat/completions"))
        connection.close.assert_called_once()

    def test_short_http_body_is_uncertain(self):
        connection = MagicMock()
        reply = connection.getresponse.return_value
        reply.read.side_effect = [b"short", b""]
        reply.getheader.return_value = "100"
        reply.getheaders.return_value = [("Content-Length", "100")]
        with patch.object(transport.http.client, "HTTPSConnection", return_value=connection):
            with self.assertRaises(transport.TransportUncertain) as raised:
                transport._exchange(b"{}", "fake-key")
        self.assertEqual(raised.exception.partial, b"short")


class PreflightTests(unittest.TestCase):
    def preflight(self, blockers):
        with patch.object(sys, "argv", ["direct_transport.py", "--preflight"]), \
             patch.object(transport, "prerequisite_blockers", return_value=blockers):
            out = io.StringIO()
            with redirect_stdout(out):
                code = transport.main()
        return code, json.loads(out.getvalue())

    def test_preflight_reports_ready_only_without_blockers(self):
        code, doc = self.preflight([])
        self.assertEqual((code, doc["status"], doc["network_attempted"]), (0, "ready", False))
        code, doc = self.preflight(["MODEL_API_KEY is not configured"])
        self.assertEqual((code, doc["status"]), (2, "blocked"))


if __name__ == "__main__":
    unittest.main()
