"""Scope and isolation regressions; never execute a candidate on the host."""
import difflib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sandbox_eval as sandbox


def changed_diff(name, source):
    original = (sandbox.ROOT / 'upstream' / name).read_text()
    return ''.join(difflib.unified_diff(original.splitlines(keepends=True), source.splitlines(keepends=True),
                                        fromfile='a/' + name, tofile='b/' + name)).encode()


class ScopeTests(unittest.TestCase):
    def test_supplied_patch_applies_exactly_without_execution(self):
        raw = (sandbox.ROOT / 'model_attempt_01' / 'MODEL_PATCH.diff').read_bytes()
        applied, scope = sandbox.review_patch(raw)
        self.assertEqual(scope['status'], 'accepted')
        for name, result in applied.items():
            self.assertEqual(result, (sandbox.ROOT / 'model_attempt_01' / name).read_bytes())

    def test_traversal_rename_binary_and_metadata_rejected(self):
        raw = (sandbox.ROOT / 'model_attempt_01' / 'MODEL_PATCH.diff').read_bytes()
        for unsafe in (raw.replace(b'a/convert_response.py', b'a/../convert_response.py'),
                       raw.replace(b'b/convert_response.py', b'b/run_trial.py'),
                       b'GIT binary patch\n', b'new file mode 120000\n' + raw,
                       raw.replace(b'--- a/', b'--- /absolute/'), raw + b'\0'):
            with self.subTest(unsafe=unsafe[:80]), self.assertRaises(sandbox.ScopeError):
                sandbox.review_patch(unsafe)

    def test_interface_extra_top_level_and_environment_access_rejected(self):
        name = 'responses_stop_details.py'
        original = (sandbox.ROOT / 'upstream' / name).read_text()
        variants = [original.replace('(response: OpenAIResponse)', '(response: OpenAIResponse, extra=None)'),
                    original + '\nopen("/tmp/executed", "w")\n',
                    original.replace('    refusals: list[str] = []', '    import os\n    refusals: list[str] = []'),
                    original.replace('    refusals: list[str] = []', '    open("/input/trial/PROTOCOL.json")\n    refusals: list[str] = []'),
                    original.replace('getattr(incomplete, "reason", None)', 'getattr(incomplete, "__class__", None)'),
                    original.replace('refusals: list[str] = []', 'refusals: list[str] = response.output')]
        for source in variants:
            with self.subTest(source=source[:100]), self.assertRaises(sandbox.ScopeError):
                sandbox.review_patch(changed_diff(name, source))

    def test_collector_behavior_cannot_change(self):
        name = 'collect_stop_details.py'
        source = (sandbox.ROOT / 'upstream' / name).read_text().replace('return details\n', 'return None\n')
        with self.assertRaisesRegex(sandbox.ScopeError, 'collector'):
            sandbox.review_patch(changed_diff(name, source))

    def test_response_mutation_and_indirect_calls_rejected(self):
        name = 'convert_response.py'
        original = (sandbox.ROOT / 'upstream' / name).read_text()
        for extra in ('response.output = []', 'response.output.append(None)',
                      '(_process_response_output_items)(response.output, tools)[0]()',
                      'global run_trial', 'len = response.output'):
            source = original.replace('    # determine the StopReason', '    ' + extra + '\n    # determine the StopReason')
            with self.subTest(extra=extra), self.assertRaises(sandbox.ScopeError):
                sandbox.review_patch(changed_diff(name, source))

    def test_loop_comprehension_and_pattern_rebindings_rejected(self):
        name = 'responses_stop_details.py'
        original = (sandbox.ROOT / 'upstream' / name).read_text()
        mutations = [
            '    for refusals in [response.output]:\n        refusals.append(None)\n',
            '    for response.output[0] in [None]:\n        pass\n',
            '    for response.output in [[]]:\n        pass\n',
            '    [None for refusals in [response.output]]\n',
            '    [None for len in [1]]\n',
            '    for StopDetails in []:\n        pass\n',
            '    match response.output:\n        case [*refusals]:\n            pass\n',
            '    match response.output:\n        case {**refusals}:\n            pass\n',
            '    match response.output:\n        case StopDetails:\n            pass\n',
        ]
        for injected in mutations:
            source = original.replace('    explanation =', injected + '\n    explanation =')
            with self.subTest(injected=injected), self.assertRaises(sandbox.ScopeError):
                sandbox.review_patch(changed_diff(name, source))

    def test_corrupt_hunks_and_partial_patch_rejected(self):
        raw = (sandbox.ROOT / 'model_attempt_01' / 'MODEL_PATCH.diff').read_bytes()
        for broken in (raw[:-1], raw.replace(b'-26,13', b'-26,99'), raw.replace(b'+26,17', b'+27,17'),
                       raw.replace(b'    if has_tool_calls:', b'    if fictional:'), raw + raw):
            with self.subTest(broken=broken[:100]), self.assertRaises(sandbox.ScopeError):
                sandbox.review_patch(broken)

    def test_source_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in sandbox.FILES:
                (root / name).symlink_to(sandbox.ROOT / 'upstream' / name)
            with self.assertRaisesRegex(sandbox.ScopeError, 'symlink'):
                sandbox.review_patch((sandbox.ROOT / 'model_attempt_01' / 'MODEL_PATCH.diff').read_bytes(), root)


class ContainerTests(unittest.TestCase):
    def test_configuration_prevents_credential_and_checkout_mounts(self):
        args = sandbox.container_command('sha256:' + 'a' * 64, '/private/tmp/disposable', 'test', 'probe')
        pairs = {args[i]: args[i+1] for i in range(len(args)-1) if args[i].startswith('--')}
        self.assertEqual(pairs['--network'], 'none')
        self.assertIn('--read-only', args)
        self.assertEqual(pairs['--user'], '65534:65534')
        self.assertEqual(pairs['--cap-drop'], 'ALL')
        self.assertEqual(pairs['--security-opt'], 'no-new-privileges:true')
        self.assertEqual(pairs['--pull'], 'never')
        self.assertEqual(pairs['--mount'], 'type=bind,src=/private/tmp/disposable,dst=/input,readonly')
        self.assertEqual(args.count('--mount'), 1)
        self.assertIn('-i', args)
        self.assertNotIn('MODEL_API_KEY', ' '.join(args))
        self.assertNotIn(str(sandbox.ROOT), ' '.join(args))

    def test_moving_image_identity_and_secret_environment_denied(self):
        with self.assertRaises(ValueError):
            sandbox.container_command('python:latest', '/tmp', 'test', 'probe')
        with patch.dict(os.environ, {'MODEL_API_KEY': 'test-secret', 'PRIVATE_TOKEN': 'test-token'}):
            self.assertNotIn('MODEL_API_KEY', sandbox._host_env())
            self.assertNotIn('PRIVATE_TOKEN', sandbox._host_env())

    def test_bad_probe_blocks_all_source_execution(self):
        inspect = {'exit_code': 0, 'failure': None,
                   'output': json.dumps([{'Id': 'sha256:' + 'a' * 64, 'RepoDigests': []}])}
        probe = {'exit_code': 1, 'failure': None, 'data': {'isolated': False}}
        with patch.object(sandbox, 'bounded_command', return_value=inspect), \
                patch.object(sandbox, '_container', return_value=probe) as container:
            result = sandbox.run_suite()
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['comparisons'], {})
        self.assertEqual(container.call_count, 1)
        self.assertEqual(container.call_args.args[2], 'probe')

    def test_missing_runtime_retains_review_but_no_execution(self):
        with patch.object(sandbox, 'bounded_command', return_value={'exit_code': 1, 'failure': None, 'output': 'missing'}), \
                patch.object(sandbox, '_container') as container:
            result = sandbox.run_suite()
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['candidates']['operator_supplied']['status'], 'reviewed')
        self.assertIsNone(result['candidates']['operator_supplied']['protocol'])
        container.assert_not_called()

    def test_bounded_reader_enforces_output_and_time_limits(self):
        output = sandbox.bounded_command([sys.executable, '-c', 'print("x"*10000)'], limit=128)
        self.assertEqual(output['failure'], 'output_limit')
        self.assertEqual(len(output['output']), 128)
        timed = sandbox.bounded_command([sys.executable, '-c', 'import time; time.sleep(3)'], timeout=0.1)
        self.assertEqual(timed['failure'], 'timeout')


if __name__ == '__main__':
    unittest.main()
