"""Offline fault injection only. All transport mocked, no real provider calls."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import meta_trial as m

class Response:
    def __init__(self,raw):self.raw=raw
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.raw[:n]

def raw(content=None,finish='stop'):
 return json.dumps({'id':'mock-only','model':m.MODEL,'usage':{'prompt_tokens':100,'completion_tokens':50,'total_tokens':150,'secret':'DO_NOT_RETAIN'},'choices':[{'finish_reason':finish,'message':{'content': content if content is not None else json.dumps({'schema':'repair-bench.a11y-proposal.v1','repair':'native_button'}),'reasoning_content':'PRIVATE_REASONING_DO_NOT_RETAIN'}}]}).encode()

class DurableAttemptTests(unittest.TestCase):
 def run_fault(self,response=None,evaluator=None,transport_error=None):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'MODEL_API_KEY':'PRIVATE_KEY_DO_NOT_RETAIN'}):
   p=Path(d)/'attempt.jsonl'
   with patch.object(m,'preflight_oracle'),patch.object(m.urllib.request,'urlopen',side_effect=transport_error,return_value=Response(response or raw())) as net,patch.object(m,'evaluate_bytes',side_effect=evaluator):
    with self.assertRaises(Exception):m.trial_once(journal_path=p)
   text=p.read_text();events=[json.loads(l) for l in text.splitlines()]
   self.assertEqual(net.call_count,1)
   for secret in ['PRIVATE_KEY_DO_NOT_RETAIN','PRIVATE_REASONING_DO_NOT_RETAIN','DO_NOT_RETAIN']:self.assertNotIn(secret,text)
   self.assertEqual(events[-1]['state'],'UNKNOWN_NO_RETRY')
   return events
 def test_browser_failure_keeps_usage_before_evaluation(self):
  ev=self.run_fault(evaluator=RuntimeError('browser down'))
  r=next(x for x in ev if x['state']=='RESPONSE_RECEIVED');self.assertEqual(r['usage']['total_tokens'],150)
  self.assertIn('CANDIDATE_PARSED',[x['state'] for x in ev])
 def test_parse_failure_keeps_identity_usage(self):
  ev=self.run_fault(response=raw('not-json'))
  self.assertEqual(next(x for x in ev if x['state']=='RESPONSE_RECEIVED')['id'],'mock-only')
 def test_truncated_response_keeps_finish_reason(self):
  ev=self.run_fault(response=raw(finish='length'))
  self.assertEqual(next(x for x in ev if x['state']=='RESPONSE_RECEIVED')['finish_reason'],'length')
 def test_transport_timeout_keeps_attempt_no_retry(self):
  ev=self.run_fault(transport_error=TimeoutError())
  self.assertIn('NETWORK_ATTEMPTED',[x['state'] for x in ev])
 def test_same_request_new_receipt_path_refuses_second_call(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'MODEL_API_KEY':'fake'}),patch.object(m,'preflight_oracle'),patch.object(m.urllib.request,'urlopen',return_value=Response(raw())) as net,patch.object(m,'evaluate_bytes',return_value={'acceptance':'ACCEPTED','checks':{}}):
   m.trial_once(journal_path=Path(d)/'one.jsonl')
   with self.assertRaises(FileExistsError):m.trial_once(journal_path=Path(d)/'two.jsonl')
   self.assertEqual(net.call_count,1)
 def test_journal_unwritable_prevents_network(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'MODEL_API_KEY':'fake'}),patch.object(m,'preflight_oracle'),patch.object(m.urllib.request,'urlopen') as net:
   p=Path(d)/'parent';p.write_text('not a directory')
   with self.assertRaises(OSError):m.trial_once(journal_path=p/'attempt.jsonl')
   net.assert_not_called()
 def test_no_journal_prevents_network(self):
  with patch.dict(os.environ,{'MODEL_API_KEY':'fake'}),patch.object(m.urllib.request,'urlopen') as net:
   with self.assertRaisesRegex(RuntimeError,'Durable journal'):m.trial_once()
   net.assert_not_called()
 def test_response_evidence_write_failure_has_prior_attempt(self):
  original=m.AttemptJournal.append
  def append(j,state,**safe):
   if state=='RESPONSE_RECEIVED':raise OSError('disk full')
   return original(j,state,**safe)
  with patch.object(m.AttemptJournal,'append',append):ev=self.run_fault()
  self.assertIn('NETWORK_ATTEMPTED',[x['state'] for x in ev])
 def test_final_receipt_write_failure_keeps_evaluated_journal(self):
  original=Path.open
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'MODEL_API_KEY':'fake'}),patch.object(m,'preflight_oracle'),patch.object(m.urllib.request,'urlopen',return_value=Response(raw())) as net,patch.object(m,'evaluate_bytes',return_value={'acceptance':'ACCEPTED','checks':{}}):
   target=Path(d)/'receipt.json'
   def open_mock(p,*a,**k):
    if p==target and a and a[0]=='x':raise OSError('simulated final write failure')
    return original(p,*a,**k)
   with patch.object(Path,'open',open_mock):self.assertEqual(m.main(['--live','--credits-confirmed','--approve-one-call',str(target)]),2)
   ev=[json.loads(l) for l in Path(str(target)+'.attempt.jsonl').read_text().splitlines()]
   self.assertEqual(ev[-1]['state'],'EVALUATED');net.assert_called_once()
 def test_request_settings_and_no_tools(self):
  p=m.request_payload();self.assertEqual(p['max_completion_tokens'],2048);self.assertEqual(p['reasoning_effort'],'low');self.assertEqual(p['response_format'],{'type':'json_object'});self.assertFalse(p['store']);self.assertNotIn('tools',p)

if __name__=='__main__':unittest.main()
