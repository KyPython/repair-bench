"""Integration tests of local HTTP trust boundaries; no Meta provider calls."""
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from server import Handler

class LocalDemoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.th = threading.Thread(target=cls.srv.serve_forever,daemon=True)
        cls.th.start()
        cls.port = cls.srv.server_port

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close(); cls.th.join(timeout=5)

    def req(self,method,path,body=None,headers=None):
        con=http.client.HTTPConnection('127.0.0.1',self.port,timeout=30)
        con.request(method,path,body=body,headers=headers or {})
        res=con.getresponse()
        out=(res.status,res.getheaders(),res.read())
        con.close();return out

    def test_real_index_and_assets(self):
        for path in ['/','/app.js','/styles.css']:
            status,headers,body=self.req('GET',path)
            self.assertEqual(status,200)
            self.assertGreater(len(body),100)
            self.assertIn('Content-Security-Policy',dict(headers))
        status,_,body=self.req('GET','/api/status')
        self.assertEqual(status,200)
        self.assertTrue(json.loads(body)['ready'])
        self.assertEqual(json.loads(body)['billing'],'none')
        self.assertFalse(json.loads(body)['provider_calls_from_ui'])

    def test_receipt_route_offline_and_not_authenticated(self):
        from unittest.mock import patch
        import os
        with patch.dict(os.environ, {}, clear=True):
            status,_,body=self.req('GET','/api/model-receipt')
            self.assertEqual(status,200)
            self.assertEqual(json.loads(body)['status'],'NOT_RECORDED')
            self.assertFalse(json.loads(body)['is_authenticated_by_app'])
            status,_,body=self.req('GET','/api/status')
            self.assertEqual(status,200)
            self.assertFalse(json.loads(body)['provider_calls_from_ui'])

    def test_three_trusted_fixture_choices(self):
        for option in ('noop','aria_only','native_button'):
            status,_,body=self.req('GET','/api/fixture?repair='+option)
            self.assertEqual(status,200)
            self.assertIn(b'Menu content',body)
        self.assertEqual(self.req('GET','/api/fixture?repair=%3Cscript%3E')[0],400)

    def test_original_world_reachable_as_separate_fixture(self):
        status,headers,html=self.req('GET','/world')
        self.assertEqual(status,200)
        self.assertIn(b'FIXTURE repair',html)
        self.assertIn('Content-Security-Policy',dict(headers))
        for name in ('/src/harness.js','/patches/cheat_autopilot.js','/tests/integrity_manifest.json'):
            self.assertEqual(self.req('GET',name)[0],200)
        self.assertEqual(self.req('GET','/patches/../../README.md')[0],404)

    def test_invalid_input_fails_closed(self):
        headers={'Content-Type':'application/json'}
        bad=['{"schema":"repair-bench.a11y-proposal.v1","repair":"script"}','{"schema":"repair-bench.a11y-proposal.v1","repair":"noop","evil":1}','not-json']
        for item in bad:
            status,_,_=self.req('POST','/api/evaluate',item,headers)
            self.assertEqual(status,422)
        self.assertEqual(self.req('POST','/api/evaluate','x'*513,headers)[0],413)
        self.assertEqual(self.req('POST','/api/evaluate','{}',{'Content-Type':'text/plain'})[0],415)
        self.assertEqual(self.req('POST','/api/evaluate','{}',{'Content-Type':'application/json','Origin':'https://evil.example'})[0],403)

    def test_real_browser_oracle_over_http(self):
        head={'Content-Type':'application/json'}
        for option,expect in [('noop','REJECTED'),('aria_only','REJECTED'),('native_button','ACCEPTED')]:
            data=json.dumps({'schema':'repair-bench.a11y-proposal.v1','repair':option})
            status,_,raw=self.req('POST','/api/evaluate',data,head)
            self.assertEqual(status,200,raw[:200])
            obj=json.loads(raw)
            self.assertEqual(obj['acceptance'],expect)
            self.assertFalse(obj['real_model_inference'])
            self.assertEqual(obj['run_provenance'],'LOCAL_CHROMIUM_OFFLINE')
            self.assertEqual(len(obj['checks']),9)

    def test_dialog_variants_over_http(self):
        for option, expected in [('noop','REJECTED'),('aria_only','REJECTED'),('managed_dialog','ACCEPTED')]:
            url='/api/fixture?task=dialog&repair='+option
            status,_,html=self.req('GET',url)
            self.assertEqual(status,200)
            self.assertIn(b'dialog-title',html)
            data=json.dumps({'task':'dialog','schema':'repair-bench.dialog-proposal.v1','repair':option})
            status,_,raw=self.req('POST','/api/evaluate',data,{'Content-Type':'application/json'})
            self.assertEqual(status,200,raw[:120]);result=json.loads(raw)
            self.assertEqual(result['task'],'dialog')
            self.assertEqual(result['acceptance'],expected)
            self.assertFalse(result['real_model_inference'])
            self.assertEqual(len(result['checks']),13)
    def test_cross_task_schema_is_rejected(self):
        headers={'Content-Type':'application/json'}
        for task,schema,repair in [('dialog','repair-bench.a11y-proposal.v1','native_button'),
                                    ('menu','repair-bench.dialog-proposal.v1','managed_dialog'),
                                    ('shell','repair-bench.a11y-proposal.v1','noop')]:
            status,_,_=self.req('POST','/api/evaluate',json.dumps({'task':task,'schema':schema,'repair':repair}),headers)
            self.assertEqual(status,422)
        self.assertEqual(self.req('GET','/api/fixture?task=dialog&repair=native_button')[0],400)
        self.assertEqual(self.req('GET','/api/fixture?task=evil')[0],400)
    def test_status_reports_both_sealed_fixtures(self):
        status,_,raw=self.req('GET','/api/status')
        self.assertEqual(status,200)
        doc=json.loads(raw)
        self.assertEqual(doc['benchmarks'],['menu','dialog'])
        self.assertEqual(len(doc['dialog_source_sha256']),64)
        self.assertFalse(doc['provider_calls_from_ui'])

if __name__ == '__main__':
    unittest.main()
