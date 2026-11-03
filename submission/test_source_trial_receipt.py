"""Separate replay tests; historical source benchmark tests remain unchanged."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import source_trial_receipt as receipt


def example():
    # Use recorded public outcomes, without executing any candidate source.
    root = Path(__file__).resolve().parents[1]
    protocol = json.loads((root/'source-repair/results.json').read_bytes())['reference']
    diff = '--- a/convert_response.py\n+++ b/convert_response.py\n<script>evil()</script>\n'
    return {'schema_version': 1, 'status': 'completed', 'blockers': [],
            'transport': {'status': 'completed', 'requested_model': 'muse-spark-1.3',
                          'returned_model': 'muse-spark-1.3', 'response_id': 'chatcmpl-test',
                          'finish_reason': 'stop', 'request_sha256': 'a'*64,
                          'usage': {'prompt_tokens': 12, 'completion_tokens': 9,
                                    'total_tokens': 21, 'completion_tokens_details': {'reasoning_tokens': 5}}},
            'comparisons': {'reference': {'protocol': protocol, 'supplemental': {'passed': 18, 'checks': 18}}},
            'candidates': {'direct_meta': {'status': 'accepted', 'provenance': 'Independent test fixture only',
                                          'patch': diff, 'patch_sha256': hashlib.sha256(diff.encode()).hexdigest(),
                                          'protocol': protocol, 'supplemental': {'passed': 18, 'checks': 18},
                                          'scope': {'approved': True},
                                          'model_statements': {'diagnosis': 'A model statement', 'risks': [], 'tests_to_run': []}}},
            'audit': {'claims': ['Operator claims are unverified'], 'limitations': ['Excerpt-level evidence']},
            'validation': {'observations': ['Test fixture observation']}}


class SourceTrialReceiptTests(unittest.TestCase):
    def test_successful_replay_keeps_nested_usage_and_inert_patch(self):
        clean = receipt.sanitize(example())
        self.assertEqual(clean['candidates']['direct_meta']['protocol']['passed'], 9)
        self.assertIn('<script>', clean['candidates']['direct_meta']['patch'])
        self.assertEqual(clean['transport']['usage']['completion_tokens_details']['reasoning_tokens'], 5)

    def test_failed_replay_preserves_failures_and_no_candidate_outcome(self):
        doc = example()
        doc.update(status='failed', blockers=['Response truncated'])
        doc['transport'].update(status='rejected', finish_reason='length')
        doc['candidates'] = {'direct_meta': {'status': 'failed', 'provenance': 'No executable candidate'}}
        clean = receipt.sanitize(doc)
        self.assertEqual(clean['transport']['finish_reason'], 'length')
        self.assertIsNone(clean['candidates']['direct_meta']['protocol'])

    def test_missing_file_has_no_model_outcome(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(receipt, 'EVIDENCE', Path(tmp)/'absent.json'):
            self.assertEqual(receipt.load_source_trial()['status'], 'missing')

    def test_invalid_and_truncated_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'evidence.json'
            for raw in ('{"schema_version":1', '[]', '{"schema_version":2}', 'null'):
                target.write_text(raw)
                with self.subTest(raw=raw), patch.object(receipt, 'EVIDENCE', target):
                    self.assertEqual(receipt.load_source_trial()['status'], 'invalid')

    def test_secret_fields_and_private_response_are_excluded(self):
        doc = example()
        secret = 'private-sentinel-do-not-display'
        doc['raw_response'] = secret
        doc['transport']['authorization'] = secret
        doc['transport']['usage']['account_id'] = 123
        doc['candidates']['direct_meta']['private_reasoning'] = secret
        doc['audit']['private_account'] = secret
        output = json.dumps(receipt.sanitize(doc))
        self.assertNotIn(secret, output)
        self.assertNotIn('account_id', output)

    def test_secret_bearing_public_text_rejected_without_echo(self):
        doc = example()
        doc['transport']['response_id'] = 'Bearer super-private-secret'
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'evidence.json'
            target.write_text(json.dumps(doc))
            with patch.object(receipt, 'EVIDENCE', target):
                output = receipt.load_source_trial()
            self.assertEqual(output['status'], 'invalid')
            self.assertNotIn('super-private-secret', json.dumps(output))

    def test_patch_hash_mismatch_rejected(self):
        doc = example()
        doc['candidates']['direct_meta']['patch_sha256'] = 'b'*64
        with self.assertRaises(ValueError):
            receipt.sanitize(doc)

    def test_inconsistent_score_rejected(self):
        doc = example()
        doc['candidates']['direct_meta']['protocol']['passed'] = 4
        with self.assertRaises(ValueError):
            receipt.sanitize(doc)

    def test_acceptance_requires_all_nine_and_scope(self):
        for key in ('scope', 'protocol'):
            doc = example()
            doc['candidates']['direct_meta'][key] = None
            with self.subTest(missing=key), self.assertRaises(ValueError):
                receipt.sanitize(doc)

    def test_duplicate_protocol_case_rejected(self):
        doc = example()
        cases = doc['candidates']['direct_meta']['protocol']['cases']
        cases[1]['case'] = cases[0]['case']
        with self.assertRaises(ValueError):
            receipt.sanitize(doc)

    def test_symlink_and_oversized_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)/'real.json'
            target.write_text(json.dumps(example()))
            link = Path(tmp)/'link.json'
            link.symlink_to(target)
            with patch.object(receipt, 'EVIDENCE', link):
                self.assertEqual(receipt.load_source_trial()['status'], 'invalid')
            target.write_bytes(b' '*1_000_001)
            with patch.object(receipt, 'EVIDENCE', target):
                self.assertEqual(receipt.load_source_trial()['status'], 'invalid')

    def test_fixed_get_route_ignores_query_paths(self):
        import server
        handler = object.__new__(server.Handler)
        calls = []
        handler.reply_json = lambda status, doc: calls.append((status, doc))
        handler.path = '/source-repair/model-trial.json?path=/private/secret'
        with patch.object(server, 'load_source_trial', return_value={'status': 'missing'}) as loader:
            handler.do_GET()
        loader.assert_called_once_with()
        self.assertEqual(calls, [(200, {'status': 'missing'})])

    def test_no_inference_execution_or_upload_routes(self):
        import server
        handler = object.__new__(server.Handler)
        calls = []
        handler.reply_json = lambda status, doc: calls.append(status)
        for path in ('/source-repair/model-trial.json', '/source-repair/execute', '/source-repair/infer'):
            handler.path = path
            handler.do_POST()
        for path in ('/source-repair/../trial/direct_meta_01/response.json', '/source-repair/execute'):
            handler.path = path
            handler.do_GET()
        self.assertEqual(calls, [404]*5)


if __name__ == '__main__':
    unittest.main()
