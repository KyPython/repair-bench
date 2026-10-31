"""Offline-only contract tests for live trial runner. Never use network."""
import json
import tempfile
import os
from pathlib import Path
import sys
import tempfile
from unittest import TestCase
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import meta_trial


class TrialContractTests(TestCase):
    def test_dry_run_has_no_network(self):
        with patch.object(meta_trial.urllib.request, 'urlopen', side_effect=AssertionError('NETWORK')):
            self.assertEqual(meta_trial.main(['--dry-run']), 0)

    def test_missing_authorization_prevents_network(self):
        with patch.object(meta_trial.urllib.request, 'urlopen', side_effect=AssertionError('NETWORK')):
            self.assertEqual(meta_trial.main(['--live', '/tmp/not-used.json']), 64)

    def test_missing_key_prevents_network(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'MODEL_API_KEY':''}):
            with patch.object(meta_trial.urllib.request, 'urlopen', side_effect=AssertionError('NETWORK')):
                self.assertEqual(meta_trial.main(['--live','--credits-confirmed','--approve-one-call',str(Path(d)/'receipt.json')]),2)
                self.assertFalse((Path(d)/'receipt.json').exists())

    def test_provider_rejects_wrong_model(self):
        sample = {'model':'wrong', 'choices':[{'finish_reason':'stop', 'message':{'content':'{}'}}]}
        with self.assertRaisesRegex(ValueError,'model identity'):
            meta_trial.parse_provider_response(json.dumps(sample).encode())

    def test_provider_rejects_nonstop(self):
        sample = {'model':meta_trial.MODEL, 'choices':[{'finish_reason':'length', 'message':{'content':'{}'}}]}
        with self.assertRaisesRegex(ValueError,'truncated'):
            meta_trial.parse_provider_response(json.dumps(sample).encode())

    def test_provider_accepts_bounded_candidate(self):
        sample = {'model':meta_trial.MODEL,'id':'mock-local-not-a-provider-receipt',
                  'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'schema':'repair-bench.a11y-proposal.v1','repair':'native_button'})}}]}
        candidate, evidence = meta_trial.parse_provider_response(json.dumps(sample).encode())
        self.assertEqual(candidate['repair'],'native_button')
        self.assertEqual(evidence['response_id'], sample['id'])

    def test_existing_receipt_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'MODEL_API_KEY':'fake-NEVER-SENT'}):
            p=Path(d)/'receipt.json'; p.write_text('existing')
            with patch.object(meta_trial.urllib.request,'urlopen', side_effect=AssertionError('NETWORK')):
                self.assertEqual(meta_trial.main(['--live','--credits-confirmed','--approve-one-call',str(p)]),64)
            self.assertEqual(p.read_text(),'existing')


class MockedProviderIntegrationTests(TestCase):
    def _mock_response(self, repair):
        data = json.dumps({'id':'mock-not-real-meta','model':meta_trial.MODEL,
                           'usage':{'total_tokens':123},'choices':[{'finish_reason':'stop',
                           'message':{'content':json.dumps({'schema':'repair-bench.a11y-proposal.v1','repair':repair})}}]}).encode()
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, count): return data[:count]
        return FakeResponse()

    def test_offline_mocked_pipeline_good(self):
        with patch.dict(os.environ, {'MODEL_API_KEY':'test-only-fake'}):
            with patch.object(meta_trial.urllib.request, 'urlopen', return_value=self._mock_response('native_button')) as transport:
                with tempfile.TemporaryDirectory() as evidence_dir:
                    result = meta_trial.trial_once(journal_path=Path(evidence_dir)/'attempt.jsonl')
                self.assertEqual(result['verification']['acceptance'],'ACCEPTED')
                self.assertEqual(result['candidate']['repair'],'native_button')
                transport.assert_called_once()  # one MOCKED invocation, no real inference

    def test_offline_mocked_pipeline_false_green_rejected(self):
        with patch.dict(os.environ, {'MODEL_API_KEY':'test-only-fake'}):
            with patch.object(meta_trial.urllib.request, 'urlopen', return_value=self._mock_response('aria_only')) as transport:
                with tempfile.TemporaryDirectory() as evidence_dir:
                    result = meta_trial.trial_once(journal_path=Path(evidence_dir)/'attempt.jsonl')
                self.assertEqual(result['verification']['acceptance'],'REJECTED')
                self.assertFalse(result['verification']['checks']['enter_activates'])
                transport.assert_called_once()  # one MOCKED invocation, no real inference
