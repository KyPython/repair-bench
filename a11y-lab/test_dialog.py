"""Independent browser tests for a genuinely different accessibility problem."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from dialog import SCHEMA,source,apply_plan,parse_proposal,evaluate_bytes,HOOK

def payload(repair):return json.dumps({'schema':SCHEMA,'repair':repair}).encode()

class DialogTests(unittest.TestCase):
    def test_managed_dialog_passes_all_real_chromium_checks(self):
        result=evaluate_bytes(payload('managed_dialog'))
        self.assertEqual(result['acceptance'],'ACCEPTED',result['checks'])
        self.assertEqual(len(result['checks']),13)
        self.assertTrue(all(result['checks'].values()))
        self.assertFalse(result['candidate_code_execution'])
    def test_aria_only_is_false_green(self):
        r=evaluate_bytes(payload('aria_only'))
        self.assertTrue(r['checks']['dialog_semantics'])
        self.assertFalse(r['checks']['focus_enters_dialog'])
        self.assertFalse(r['checks']['escape_closes'])
        self.assertEqual(r['acceptance'],'REJECTED')
    def test_unmodified_dialog_fails_and_pointer_remains_functional(self):
        r=evaluate_bytes(payload('noop'))
        self.assertTrue(r['checks']['pointer_opens'])
        self.assertTrue(r['checks']['pointer_closes'])
        self.assertFalse(r['checks']['dialog_semantics'])
        self.assertEqual(r['acceptance'],'REJECTED')
    def test_schema_rejects_injected_code_and_extra_key(self):
        for raw in [b'<script>alert(1)</script>',payload('managed_dialog').replace(b'"repair"',b'"evil"'),
                    json.dumps({'schema':SCHEMA,'repair':'managed_dialog','override':True}).encode()]:
            with self.assertRaises(ValueError):parse_proposal(raw)
    def test_predeclared_patch_changes_only_expected_source_spans(self):
        original=source()
        self.assertIn(HOOK,original)
        fixed=apply_plan(original,'managed_dialog')
        self.assertNotIn(HOOK,fixed)
        self.assertIn('outside.inert=true',fixed)
        self.assertEqual(apply_plan(original,'noop'),original)
    def test_tamper_detection_refuses_modified_fixture(self):
        from tempfile import TemporaryDirectory
        import dialog
        # Tamper with source bytes, without altering canonical files.
        with patch.object(dialog.Path,'read_bytes',return_value=b'<script>malicious</script>'):
            with self.assertRaisesRegex(ValueError,'SEAL_FAIL'):
                dialog.source()

if __name__=='__main__':unittest.main()
