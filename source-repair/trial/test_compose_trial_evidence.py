"""Composer tests use recorded public outcomes and fixtures; no network."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compose_trial_evidence as compose

ROOT = Path(__file__).resolve().parents[2]
REF = json.loads((ROOT / "source-repair/results.json").read_bytes())["reference"]
SUPP = {"passed": 18, "checks": 18}
PATCH = "--- a/convert_response.py\n+++ b/convert_response.py\n@@ -1 +1 @@\n-old\n+new\n"


def attempt(tmp, status="response_validated_unexecuted", error=None):
    attempt_dir = Path(tmp) / "direct_meta_01"
    attempt_dir.mkdir()
    (attempt_dir / "manifest.json").write_text(json.dumps(
        {"requested_model": "muse-spark-1.3", "reserved_utc": "2026-11-03T00:00:00+00:00",
         "request_sha256": "b" * 64}))
    if status is not None:
        summary = {"status": status, "requested_model": "muse-spark-1.3",
                   "returned_model": "muse-spark-1.3", "response_id": "chatcmpl-test",
                   "provider_request_id": "req-test", "finish_reason": "stop",
                   "sent_utc": "2026-11-03T00:00:01+00:00",
                   "received_utc": "2026-11-03T00:00:02+00:00",
                   "request_sha256": "b" * 64, "response_sha256": "a" * 64,
                   "patch_sha256": hashlib.sha256(PATCH.encode()).hexdigest(),
                   "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        if error:
            summary["error"] = error
        (attempt_dir / "transport.json").write_text(json.dumps(summary))
    return attempt_dir


def authorize_private(attempt_dir):
    private = attempt_dir.parent / ".private" / attempt_dir.name
    private.mkdir(parents=True)
    (private / "MODEL_PATCH.diff").write_text(PATCH)
    (private / "proposal.json").write_text(json.dumps(
        {"diagnosis": "Fixture diagnosis", "risks": ["Fixture risk"],
         "tests_to_run": ["Frozen checks in a sandbox"]}))


def sandbox(tmp, status="completed"):
    operator_patch = (ROOT / "source-repair/model_attempt_01/MODEL_PATCH.diff").read_bytes()
    report = {
        "status": status, "blockers": [], "comparators_reproduced": status == "completed",
        "image": {"id": "sha256:" + "c" * 64}, "probe": {"data": {"isolated": True}},
        "comparisons": {branch: {"protocol": REF, "supplemental": SUPP}
                        for branch in ("upstream", "reference")},
        "candidates": {
            "operator_supplied": {
                "status": "accepted", "patch_sha256": hashlib.sha256(operator_patch).hexdigest(),
                "protocol": REF, "supplemental": SUPP,
                "scope": {"status": "accepted", "approved": True, "review": "Fixture review"}},
            "direct_meta": {
                "status": "accepted", "patch_sha256": hashlib.sha256(PATCH.encode()).hexdigest(),
                "protocol": REF, "supplemental": SUPP,
                "scope": {"status": "accepted", "approved": True, "review": "Fixture review"}}}}
    path = Path(tmp) / "sandbox.json"
    path.write_text(json.dumps(report))
    return path


class ComposeTests(unittest.TestCase):
    def test_completed_trial_replays_real_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt_dir = attempt(tmp)
            authorize_private(attempt_dir)
            doc = compose.compose(attempt_dir, sandbox(tmp))
        self.assertEqual(doc["status"], "completed")
        self.assertEqual(doc["transport"]["status"], "completed")
        self.assertEqual(doc["transport"]["response_id"], "chatcmpl-test")
        direct = doc["candidates"]["direct_meta"]
        self.assertEqual(direct["status"], "accepted")
        self.assertEqual(direct["patch"], PATCH)
        self.assertEqual(direct["model_statements"]["diagnosis"], "Fixture diagnosis")
        self.assertEqual(direct["protocol"]["passed"], 9)
        self.assertEqual(doc["candidates"]["operator_supplied"]["status"], "accepted")
        self.assertEqual(doc["comparisons"]["reference"]["supplemental"]["passed"], 18)
        self.assertTrue(doc["audit"]["claims"])

    def test_blocked_trial_without_send_or_sandbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt_dir = attempt(tmp, status=None)
            doc = compose.compose(attempt_dir, None)
        self.assertEqual(doc["status"], "blocked")
        self.assertEqual(doc["transport"]["status"], "not_sent")
        self.assertIsNone(doc["candidates"]["direct_meta"]["patch"])
        self.assertEqual(doc["candidates"]["direct_meta"]["status"], "unavailable")
        self.assertTrue(doc["blockers"])
        # The operator patch is public evidence even without any sandbox run.
        self.assertIn("convert_response.py", doc["candidates"]["operator_supplied"]["patch"])

    def test_second_attempt_replays_scope_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt_dir = attempt(tmp)
            authorize_private(attempt_dir)
            second = Path(tmp) / "direct_meta_02"
            second.mkdir()
            (second / "manifest.json").write_text(json.dumps(
                {"requested_model": "muse-spark-1.3", "reserved_utc": "2026-11-03T01:00:00+00:00",
                 "request_sha256": "d" * 64}))
            (second / "transport.json").write_text(json.dumps(
                {"status": "response_validated_unexecuted", "requested_model": "muse-spark-1.3",
                 "returned_model": "muse-spark-1.3", "response_id": "chatcmpl-second",
                 "finish_reason": "stop", "sent_utc": "2026-11-03T01:00:01+00:00",
                 "received_utc": "2026-11-03T01:00:02+00:00",
                 "request_sha256": "d" * 64, "response_sha256": "e" * 64,
                 "patch_sha256": hashlib.sha256(PATCH.encode()).hexdigest(),
                 "usage": {"prompt_tokens": 5, "total_tokens": 9}}))
            (second / "scope_review.json").write_text(json.dumps(
                {"attempt": "direct_meta_02", "executed": False,
                 "patch_sha256": hashlib.sha256(PATCH.encode()).hexdigest(),
                 "scope": {"approved": False, "status": "rejected",
                           "reason": "Hunk context mismatch"}}))
            authorize_private(second)
            doc = compose.compose(attempt_dir, sandbox(tmp), audit_path=compose.TRIAL / "OPERATOR_ATTEMPT_AUDIT.json", attempt2_dir=second)
        self.assertEqual(doc["transport_02"]["response_id"], "chatcmpl-second")
        replayed = doc["candidates"]["direct_meta_02"]
        self.assertEqual(replayed["status"], "rejected")
        self.assertFalse(replayed["scope"]["approved"])
        self.assertIn("Hunk context mismatch", replayed["scope"]["reasons"])
        self.assertIsNone(replayed["protocol"])
        self.assertEqual(replayed["patch"], PATCH)
        self.assertEqual(replayed["model_statements"]["diagnosis"], "Fixture diagnosis")
        self.assertIn("direct_meta_02 candidate status: rejected", doc["validation"]["observations"])
        # The first attempt is untouched by the second.
        self.assertEqual(doc["candidates"]["direct_meta"]["status"], "accepted")
        self.assertEqual(doc["transport"]["response_id"], "chatcmpl-test")

    def test_second_attempt_fingerprint_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt_dir = attempt(tmp)
            authorize_private(attempt_dir)
            second = Path(tmp) / "direct_meta_02"
            second.mkdir()
            (second / "manifest.json").write_text(json.dumps(
                {"requested_model": "muse-spark-1.3", "request_sha256": "d" * 64}))
            (second / "transport.json").write_text(json.dumps(
                {"status": "response_validated_unexecuted",
                 "patch_sha256": "0" * 64}))
            (second / "scope_review.json").write_text(json.dumps(
                {"attempt": "direct_meta_02", "executed": False,
                 "patch_sha256": hashlib.sha256(PATCH.encode()).hexdigest(),
                 "scope": {"approved": False, "status": "rejected"}}))
            authorize_private(second)
            with self.assertRaises(compose.ComposeError):
                compose.compose(attempt_dir, sandbox(tmp), attempt2_dir=second)

    def test_rejected_transport_exports_no_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt_dir = attempt(tmp, status="rejected", error="malformed_json")
            doc = compose.compose(attempt_dir, None)
        self.assertEqual(doc["transport"]["status"], "rejected")
        self.assertIsNone(doc["candidates"]["direct_meta"]["patch"])
        self.assertNotIn("model_statements", doc["candidates"]["direct_meta"])
        self.assertTrue(any("malformed_json" in item for item in doc["blockers"]))

    def test_patch_fingerprint_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt_dir = attempt(tmp)
            authorize_private(attempt_dir)
            summary = json.loads((attempt_dir / "transport.json").read_text())
            summary["patch_sha256"] = "0" * 64
            (attempt_dir / "transport.json").write_text(json.dumps(summary))
            with self.assertRaises(compose.ComposeError):
                compose.compose(attempt_dir, sandbox(tmp))

    def test_missing_audit_and_sandbox_fail_open_with_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            attempt_dir = attempt(tmp, status=None)
            doc = compose.compose(attempt_dir, None, Path(tmp) / "absent_audit.json")
        self.assertEqual(doc["status"], "blocked")
        self.assertEqual(doc["audit"]["claims"], [])

    def test_symlink_and_oversized_inputs_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.json"
            real.write_text("{}")
            link = Path(tmp) / "link.json"
            link.symlink_to(real)
            with self.assertRaises(compose.ComposeError):
                compose.compose(Path(tmp) / "absent", link)
            big = Path(tmp) / "big.json"
            big.write_bytes(b" " * (compose.LIMIT + 1))
            with self.assertRaises(compose.ComposeError):
                compose.compose(Path(tmp) / "absent", big)

    def test_cli_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "model-trial.json"
            out.write_text("{}")
            with patch.object(sys, "argv", ["compose", "--out", str(out)]):
                with self.assertRaises(SystemExit):
                    compose.main()
            self.assertEqual(out.read_text(), "{}")


if __name__ == "__main__":
    unittest.main()
