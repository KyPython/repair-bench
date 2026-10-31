"""No live provider calls: proves the second benchmark's API and reject behavior."""
import json
import tempfile
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import meta_trial

class DialogTrialTests(unittest.TestCase):
    def test_dry_run_does_not_call_provider(self):
        with patch.object(meta_trial.urllib.request,'urlopen',side_effect=AssertionError('provider network forbidden')):
            self.assertEqual(meta_trial.main(['--dry-run','--task','dialog']),0)
    def test_provider_schema_separated_by_task(self):
        payload=lambda repair,schema:json.dumps({'model':meta_trial.MODEL,'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'schema':schema,'repair':repair})}}]}).encode()
        candidate,_=meta_trial.parse_provider_response(payload('managed_dialog','repair-bench.dialog-proposal.v1'),'dialog')
        self.assertEqual(candidate['repair'],'managed_dialog')
        with self.assertRaises(ValueError):meta_trial.parse_provider_response(payload('native_button','repair-bench.a11y-proposal.v1'),'dialog')
    def test_no_key_and_no_live_flag_reject_network(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(meta_trial.os.environ,{'MODEL_API_KEY':''}):
            path=str(Path(d)/'fake.json')
            with patch.object(meta_trial.urllib.request,'urlopen',side_effect=AssertionError('provider network forbidden')):
                self.assertEqual(meta_trial.main(['--live','--credits-confirmed','--approve-one-call',path,'--task','dialog']),2)
                self.assertEqual(meta_trial.main(['--live','--approve-one-call',path,'--task','dialog']),64)
    def test_mock_provider_dialog_pipeline_uses_real_browser(self):
        doc={'model':meta_trial.MODEL,'id':'SYNTHETIC-MOCK-NOT-PROVIDER','choices':[{'finish_reason':'stop','message':{'content':json.dumps({'schema':'repair-bench.dialog-proposal.v1','repair':'managed_dialog'})}}]}
        raw=json.dumps(doc).encode()
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return raw[:n]
        with patch.dict(meta_trial.os.environ,{'MODEL_API_KEY':'local-fake-token'}):
            with patch.object(meta_trial.urllib.request,'urlopen',return_value=Response()) as stub:
                with tempfile.TemporaryDirectory() as evidence_dir:
                    result=meta_trial.trial_once('dialog',Path(evidence_dir)/'attempt.jsonl')
        self.assertEqual(result['task'],'dialog')
        self.assertEqual(result['verification']['acceptance'],'ACCEPTED')
        stub.assert_called_once()

if __name__=='__main__':unittest.main()
