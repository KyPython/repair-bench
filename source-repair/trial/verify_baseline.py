#!/usr/bin/env python3
"""Run the original 84 checks in a disposable, credential-free project copy.

This runs trusted original tests only. Candidate evaluation belongs exclusively
to sandbox_eval.py. Historical evidence written by tests stays in the copy.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
INVENTORY = Path(__file__).with_name('PROTECTED_SHA256.json')


def verify_protected():
    expected = json.loads(INVENTORY.read_bytes())
    changed = [name for name, digest in expected.items()
               if not (ROOT/name).is_file() or hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest]
    return {'files': len(expected), 'unchanged': not changed, 'changed': changed}


def run(chromium=None):
    protected_before = verify_protected()
    if not protected_before['unchanged']:
        raise ValueError('Protected bytes changed')
    original = json.loads(INVENTORY.read_bytes())
    with tempfile.TemporaryDirectory(prefix='repair-bench-baseline-') as directory:
        copy = Path(directory)/'project'
        copy.mkdir()
        for folder in ['src', 'patches', 'tests', 'defined-request', 'a11y-lab', 'submission', 'source-repair']:
            for path in (ROOT/folder).rglob('*'):
                relative = path.relative_to(ROOT)
                if (not path.is_file() or path.is_symlink() or
                    any(p.startswith('.') or p == '__pycache__' for p in relative.parts) or
                    path.suffix == '.pyc' or 'model_attempt_01' in relative.parts or
                    'direct_meta_01' in relative.parts):
                    continue
                # New tests have their own verification; freeze original counts.
                if path.name.startswith('test_') and str(relative) not in original:
                    continue
                target = copy/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
        for name in ['index.html', 'LICENSE']:
            shutil.copyfile(ROOT/name, copy/name)
        clean_env = {'PATH': os.defpath, 'PYTHONNOUSERSITE': '1',
                     'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(copy/'submission'),
                     'TMPDIR': directory, 'LANG': 'en_US.UTF-8'}
        if chromium:
            clean_env['RB_CHROMIUM'] = str(Path(chromium).resolve())
        node = shutil.which('node')
        if not node:
            raise ValueError('Node unavailable')
        commands = [
            ('world', 16, [node, 'tests/run_tests.js']),
            ('mapping', 11, [node, '--test', 'tests/evaluate_mapping.test.js']),
            ('accessibility', 37, [sys.executable, '-m', 'unittest', 'discover', '-s', 'a11y-lab', '-p', 'test_*.py', '-v']),
            ('submission', 20, [sys.executable, '-m', 'unittest', 'discover', '-s', 'submission', '-p', 'test_*.py', '-v']),
        ]
        results = []
        for label, count, command in commands:
            try:
                result = subprocess.run(command, cwd=copy, env=clean_env,
                                        capture_output=True, text=True, timeout=240)
                results.append({'suite': label, 'expected_checks': count,
                                'exit_code': result.returncode,
                                'stdout': result.stdout[-80000:], 'stderr': result.stderr[-80000:]})
            except subprocess.TimeoutExpired:
                results.append({'suite': label, 'expected_checks': count,
                                'exit_code': None, 'error': 'timeout'})
        return {'timestamp_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                'trusted_baseline_only': True, 'disposable_copy': True,
                'clean_environment_keys': sorted(clean_env),
                'browser_binary': chromium, 'expected_checks': 84,
                'all_commands_passed': all(r['exit_code'] == 0 for r in results),
                'suites': results, 'protected_before': protected_before,
                'protected_after': verify_protected()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chromium')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = run(args.chromium)
    # New validation outputs only; refuse to overwrite any existing artifact.
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print(json.dumps({k: report[k] for k in ['expected_checks', 'all_commands_passed', 'protected_after']}))
    sys.exit(0 if report['all_commands_passed'] and report['protected_after']['unchanged'] else 1)
