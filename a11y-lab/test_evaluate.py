"""GPT-6 2026-10-28 — offline trust-boundary and browser tests."""
import json
from pathlib import Path
import unittest
from evaluate import evaluate_bytes, parse_proposal, prompt, source, apply_plan


def payload(kind):
    return json.dumps({'schema':'repair-bench.a11y-proposal.v1', 'repair':kind}).encode('utf-8')


class RepairBenchA11yTests(unittest.TestCase):
    def test_native_button_accepted(self):
        r=evaluate_bytes(payload('native_button'))
        self.assertEqual(r['acceptance'],'ACCEPTED')
        self.assertTrue(all(r['checks'].values()))
        self.assertFalse(r['real_model_inference'])
        self.assertFalse(r['candidate_code_execution'])

    def test_aria_only_false_green_rejected(self):
        r=evaluate_bytes(payload('aria_only'))
        self.assertEqual(r['acceptance'],'REJECTED')
        self.assertTrue(r['checks']['keyboard_reaches_trigger'])
        self.assertFalse(r['checks']['enter_activates'])

    def test_noop_rejected(self):
        r=evaluate_bytes(payload('noop'))
        self.assertEqual(r['acceptance'],'REJECTED')
        self.assertTrue(r['checks']['mouse_opens'])
        self.assertFalse(r['checks']['keyboard_reaches_trigger'])

    def test_untrusted_script_rejected(self):
        with self.assertRaisesRegex(ValueError,'JSON'):
            parse_proposal(b'__import__("os").system("exit 1")')

    def test_extra_field_rejected(self):
        with self.assertRaisesRegex(ValueError,'exactly'):
            parse_proposal(json.dumps({'schema':'repair-bench.a11y-proposal.v1','repair':'native_button','test_override':True}).encode())

    def test_oversize_rejected(self):
        with self.assertRaisesRegex(ValueError,'limit'):
            parse_proposal(b'x'*2049)

    def test_baseline_sealed_and_prompt_has_no_oracle(self):
        self.assertIn('data-repair-target',source())
        self.assertNotIn('focus_restored', prompt())
        self.assertNotIn('browser_checks', prompt())
        self.assertNotIn('test_evaluate.py',prompt())

    def test_only_target_changes(self):
        s=source(); fixed=apply_plan(s,'native_button')
        self.assertIn('<button type="button" id="open-menu"',fixed)
        self.assertIn('<section id="panel"',fixed)
        self.assertEqual(s.replace('<div id="open-menu" data-repair-target="menu-trigger" aria-expanded="false" aria-controls="panel">Open menu</div>',''), fixed.replace('<button type="button" id="open-menu" data-repair-target="menu-trigger" aria-expanded="false" aria-controls="panel">Open menu</button>',''))


if __name__ == '__main__':
    unittest.main()
