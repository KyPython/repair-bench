"""Source-repair extension tests; source derived from Inspect AI issue #5971.

These are function-excerpt checks, not an upstream installation.
"""
import hashlib
import json
from pathlib import Path
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source-repair' / 'trial'))
from run_trial import fnv32, run, PROTOCOL


class SourceRepairReplayTests(unittest.TestCase):
    def test_exact_upstream_snippets_verified(self):
        folder=ROOT/'source-repair'/'upstream'
        for filename,expected in PROTOCOL['selected_source_functions_fnv32'].items():
            with self.subTest(filename=filename):
                self.assertEqual(fnv32((folder/filename).read_bytes()),expected)

    def test_original_reproduces_meaningful_failure(self):
        result=run(ROOT/'source-repair'/'upstream')
        self.assertEqual(result['passed'],4)
        filtered=next(c for c in result['cases'] if c['case']=='filtered_tool')
        self.assertFalse(filtered['passed'])
        self.assertEqual(filtered['observed']['tool_call_count'],1)
        self.assertIsNone(filtered['observed']['details_type'])

    def test_reference_passes_without_losing_normal_tools(self):
        result=run(ROOT/'source-repair'/'reference')
        self.assertEqual(result['passed'],9)
        normal=next(c for c in result['cases'] if c['case']=='normal_tool')
        self.assertTrue(normal['observed']['dispatch'])
        for c in result['cases']:
            if c['case'].startswith(('filtered','truncated')):
                self.assertFalse(c['observed']['dispatch'])

    def test_each_partial_repair_is_rejected(self):
        for variant in ['cosmetic','stoponly','toolsonly']:
            with self.subTest(variant=variant):
                result=run(ROOT/'source-repair'/variant)
                self.assertLess(result['passed'],result['total'])
                self.assertFalse(next(c for c in result['cases'] if c['case']=='filtered_tool')['passed'])

    def test_read_only_evidence_page_does_not_create_model_endpoint(self):
        import server
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            port=http.server_port
            for route in ['/source-repair','/source-repair/app.js','/source-repair/styles.css','/source-repair/results.json']:
                with self.subTest(route=route), urlopen(f'http://127.0.0.1:{port}{route}',timeout=10) as response:
                    self.assertEqual(response.status,200)
                    self.assertIn("script-src 'self'",response.headers['Content-Security-Policy'])
                    raw=response.read()
                    self.assertGreater(len(raw),100)
                    if route.endswith('results.json'):
                        data=json.loads(raw)
                        self.assertEqual(data['reference']['passed'],9)
                        self.assertEqual(data['upstream']['passed'],4)
        finally:
            http.shutdown();http.server_close();thread.join(timeout=5)

if __name__ == '__main__': unittest.main()
