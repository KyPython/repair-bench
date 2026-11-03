"""Attempt-02 transport tests; all provider traffic is fake and no code executes.

Covers the 02-specific gates (new request bytes, 02 scope, 02 attempt path) plus
one mocked end-to-end send. Parsing edge cases are identical to attempt 01 and
stay covered by test_direct_transport.py.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest.mock import patch

import direct_transport as transport01
import direct_transport_02 as transport


PROPOSAL = {"diagnosis": "A proposal only; tests have not run.",
            "patch": "--- a/convert_response.py\n+++ b/convert_response.py\n@@ -1 +1 @@\n-old\n+new\n",
            "risks": ["Excerpt-level proposal"], "tests_to_run": ["Frozen checks in a sandbox"]}


def response(**changes):
    doc = {"id": "chatcmpl-test-2", "model": transport.MODEL,
           "choices": [{"index": 0, "finish_reason": "stop", "message": {
               "role": "assistant", "content": json.dumps(PROPOSAL)}}],
           "usage": {"prompt_tokens": 42, "completion_tokens": 20, "total_tokens": 62}}
    doc.update(changes)
    return json.dumps(doc).encode()


class Transport02Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="source-transport02-test-")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        paths = ["source-repair/trial/PROTOCOL.json", "source-repair/trial/run_trial.py",
                 "source-repair/trial/metamorphic.py", "source-repair/trial/PROTECTED_SHA256.json",
                 "source-repair/trial/direct_transport_02.py", "docs/META_SOURCE_REPAIR_SPEC.md"]
        paths += ["source-repair/upstream/" + n for n in transport.SOURCE_NAMES]
        for relative in paths:
            destination = self.repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(transport.ROOT / relative, destination)
        self.attempt = self.repo / "source-repair/trial/direct_meta_02"

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

    def test_attempt_01_module_untouched(self):
        self.assertEqual(transport01.AUTH_SCOPE,
                         "direct_meta_01 single send, n=1, max_completion_tokens=8192, no retries")
        self.assertEqual(transport01.DEFAULT_ATTEMPT.name, "direct_meta_01")
        self.assertEqual(transport.AUTH_SCOPE,
                         "direct_meta_02 single send, n=1, max_completion_tokens=8192, no retries")
        self.assertEqual(transport.DEFAULT_ATTEMPT.name, "direct_meta_02")

    def test_request_is_new_deterministic_and_exactly_configured(self):
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
        self.assertIn(transport.DIFF_FORMAT, prompt)
        self.assertIn(transport.UPSTREAM_REVISION, prompt)
        self.assertNotIn("MODEL_PATCH.diff", prompt)
        self.assertNotIn("model_attempt_01", prompt)
        self.assertNotIn("direct_meta_01", prompt)
        # New bytes, not a resend of attempt 01.
        old = transport01.request_bytes(transport01.ROOT)
        self.assertNotEqual(first, old)
        self.assertNotEqual(hashlib.sha256(first).hexdigest(),
                            "f122a2a0cea4518b366b3e49a74d7be45ccf9ba8c4ec5d5d889df0eddd9d79b4")

    def test_source_mutation_blocks_preparation(self):
        (self.repo / "source-repair/upstream/convert_response.py").write_text("changed")
        with self.assertRaisesRegex(transport.TransportDenied, "frozen_input_mismatch"):
            self.reserve()
        self.assertFalse(self.attempt.exists())

    def test_wrong_attempt_path_denied(self):
        wrong = self.repo / "source-repair/trial/direct_meta_01"
        with self.assertRaisesRegex(transport.TransportDenied, "unexpected_attempt_path"):
            transport.reserve_attempt(wrong, self.repo)
        with self.assertRaisesRegex(transport.TransportDenied, "unexpected_attempt_path"):
            transport.send_reserved(wrong, self.repo)
        self.assertFalse(wrong.exists())

    def test_exclusive_reservation_keeps_exact_bytes(self):
        manifest = self.reserve()
        raw = (self.attempt / "request.json").read_bytes()
        self.assertEqual(raw, transport.request_bytes(self.repo))
        self.assertEqual(manifest["attempt"], "direct_meta_02")
        self.assertEqual(manifest["request_sha256"], hashlib.sha256(raw).hexdigest())
        with self.assertRaises(FileExistsError):
            self.reserve()
        self.assertEqual((self.attempt / "request.json").read_bytes(), raw)

    def test_missing_credentials_and_billing_deny_without_transport(self):
        self.reserve()
        with patch.dict(os.environ, {}, clear=True), patch.object(transport, "_exchange") as exchange:
            self.assertEqual(len(transport.prerequisite_blockers(self.attempt)), 2)
            with self.assertRaises(transport.TransportDenied):
                transport.send_reserved(self.attempt, self.repo)
        exchange.assert_not_called()
        events = (self.attempt / "events.jsonl").read_text()
        self.assertIn('"network_attempted":false', events)
        self.assertNotIn('"network_attempted":true', events)

    def test_attempt_01_scope_authorization_rejected_for_02(self):
        self.reserve()
        self.authorize(scope=transport01.AUTH_SCOPE)
        self.assertFalse(transport._verify_owner_billing_authorization(self.attempt))
        with patch.dict(os.environ, {"MODEL_API_KEY": "fake-key"}, clear=True):
            self.assertEqual(len(transport.prerequisite_blockers(self.attempt)), 1)
        self.authorize()
        self.assertTrue(transport._verify_owner_billing_authorization(self.attempt))
        with patch.dict(os.environ, {"MODEL_API_KEY": "fake-key"}, clear=True):
            self.assertEqual(transport.prerequisite_blockers(self.attempt), [])

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

    def test_mocked_send_records_private_bytes_under_02_paths(self):
        self.reserve()
        self.authorize()
        raw = response()
        with patch.dict(os.environ, {"MODEL_API_KEY": "unit-test-secret-do-not-export"}, clear=True), \
             patch.object(transport, "_exchange",
                          return_value=(200, {"x-request-id": "req-test-02"}, raw)) as exchange:
            summary = transport.send_reserved(self.attempt, self.repo)
        self.assertEqual(exchange.call_count, 1)
        self.assertEqual(summary["status"], "response_validated_unexecuted")
        private = self.attempt.parent / ".private/direct_meta_02"
        self.assertEqual((private / "response.bin").read_bytes(), raw)
        self.assertEqual((private / "MODEL_PATCH.diff").read_text(), PROPOSAL["patch"])
        self.assertEqual(stat.S_IMODE(private.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((private / "response.bin").stat().st_mode), 0o600)
        public = (self.attempt / "transport.json").read_text()
        self.assertNotIn("unit-test-secret-do-not-export", public)
        self.assertNotIn(PROPOSAL["diagnosis"], public)


if __name__ == "__main__":
    unittest.main()
