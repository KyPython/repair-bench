#!/usr/bin/env python3
"""Review excerpt diffs without executing them; evaluate only inside Docker.

This is deliberately a conservative syntax/scope gate, not a general Python
security proof. Container isolation remains mandatory after the gate passes.
No source from a candidate is imported, compiled or executed on the host.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import tempfile
import time
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FILES = ('convert_response.py', 'responses_stop_details.py', 'collect_stop_details.py')
COMPARATORS = {'upstream': 4, 'reference': 9, 'cosmetic': 5, 'stoponly': 4, 'toolsonly': 4}
LIMIT = 512 * 1024
CLEAN_ENV = {
    'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/nonexistent',
    'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
    'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
}


class ScopeError(ValueError):
    pass


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _read_file(path):
    if path.is_symlink() or not path.is_file():
        raise ScopeError('Regular non-symlink source required')
    return path.read_bytes()


def _function(raw):
    try:
        tree = ast.parse(raw.decode('utf-8'))
    except (SyntaxError, UnicodeError, RecursionError) as exc:
        raise ScopeError('Invalid Python excerpt') from exc
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        raise ScopeError('Exactly the supplied top-level function is permitted')
    return tree.body[0]


def _signature(fn):
    return (fn.name, ast.dump(fn.args), ast.dump(fn.returns),
            tuple(ast.dump(d) for d in fn.decorator_list), fn.type_comment)


def _review_source(name, original, proposed):
    before, after = _function(original), _function(proposed)
    if _signature(before) != _signature(after):
        raise ScopeError('Function interface changed')
    if name == 'collect_stop_details.py':
        if ast.dump(before) != ast.dump(after):
            raise ScopeError('Shared collector behavior changed')
        return
    calls = {'len', 'isinstance', 'getattr', 'bool', 'StopDetails',
             'ChatMessageAssistant', '_process_response_output_items'}
    # Attribute calls are restricted to the original known pure/string and
    # local-list expressions. In particular no response/global mutation call.
    original_methods = {ast.dump(n.func) for n in ast.walk(before)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    original_attrs = {n.attr for n in ast.walk(before) if isinstance(n, ast.Attribute)}
    forbidden = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.ClassDef,
                 ast.AsyncFunctionDef, ast.Lambda, ast.With, ast.AsyncWith,
                 ast.Delete, ast.Yield, ast.YieldFrom, ast.Await, ast.NamedExpr,
                 ast.Try)
    accumulator_target = None
    if name == 'responses_stop_details.py':
        declarations = [n for n in ast.walk(after) if isinstance(n, (ast.Assign, ast.AnnAssign))
                        and any(isinstance(t, ast.Name) and t.id == 'refusals'
                                for target in (n.targets if isinstance(n, ast.Assign) else [n.target])
                                for t in ast.walk(target))]
        if len(declarations) != 1 or not isinstance(declarations[0].value, ast.List) or declarations[0].value.elts:
            raise ScopeError('Refusal accumulator must remain a fresh empty local list')
        declaration = declarations[0]
        targets = declaration.targets if isinstance(declaration, ast.Assign) else [declaration.target]
        if len(targets) != 1 or not isinstance(targets[0], ast.Name) or targets[0].id != 'refusals':
            raise ScopeError('Refusal accumulator declaration must be direct')
        accumulator_target = targets[0]
    for node in ast.walk(after):
        if isinstance(node, forbidden) or (isinstance(node, ast.FunctionDef) and node is not after):
            raise ScopeError('Unexpected executable construct')
        if isinstance(node, ast.Name) and ('__' in node.id or node.id in
                {'open', 'eval', 'exec', 'compile', 'globals', 'locals', 'vars',
                 'setattr', 'delattr', 'input', 'breakpoint', 'run_trial', 'metamorphic'}):
            raise ScopeError('Evaluator or ambient environment access')
        if isinstance(node, ast.Attribute) and (node.attr not in original_attrs or '__' in node.attr):
            raise ScopeError('Unexpected attribute access')
        # Store contexts cover assignment, augmented assignment, loop targets
        # and comprehension targets, including destructuring. Patterns bind
        # string names rather than Name(Store) nodes and need their own check.
        if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(node.ctx, ast.Store):
            raise ScopeError('Mutation outside local variables')
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id in calls:
                raise ScopeError('Rebinding dependency')
            if node.id == 'refusals' and node is not accumulator_target:
                raise ScopeError('Rebinding refusal accumulator')
        bindings = []
        if isinstance(node, (ast.MatchAs, ast.MatchStar, ast.ExceptHandler)):
            bindings.append(node.name)
        if isinstance(node, ast.MatchMapping):
            bindings.append(node.rest)
        if any(bound in calls or bound == 'refusals' for bound in bindings if bound):
            raise ScopeError('Rebinding protected name through pattern or exception')
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if any(isinstance(t, (ast.Attribute, ast.Subscript)) for t in ast.walk(target)):
                    raise ScopeError('Mutation outside local variables')
                if any(isinstance(t, ast.Name) and t.id in calls for t in ast.walk(target)):
                    raise ScopeError('Rebinding dependency')
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id not in calls:
                    raise ScopeError('Unexpected function call')
                if node.func.id == 'getattr':
                    # No computed attribute names, even for a nominally safe builtin.
                    if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant) or node.args[1].value != 'reason':
                        raise ScopeError('Unexpected dynamic attribute access')
            elif isinstance(node.func, ast.Attribute):
                if ast.dump(node.func) not in original_methods:
                    raise ScopeError('Unexpected method side effect')
            else:
                raise ScopeError('Indirect call')


def review_patch(patch: bytes, upstream: Path = ROOT / 'upstream'):
    """Strictly apply a diff to in-memory bytes and inspect AST, never exec it."""
    if not patch or len(patch) > 128 * 1024 or b'\0' in patch:
        raise ScopeError('Empty, oversized or binary patch')
    try:
        text = patch.decode('utf-8')
    except UnicodeError as exc:
        raise ScopeError('Patch must be UTF-8') from exc
    if '\r' in text or not text.endswith('\n'):
        raise ScopeError('Patch must use complete LF lines')
    sources = {name: _read_file(upstream / name) for name in FILES}
    originals = dict(sources)
    lines = text.splitlines(keepends=True)
    index, changed = 0, set()
    while index < len(lines):
        if lines[index].startswith('diff --git '):
            m = re.fullmatch(r'diff --git a/([a-z_]+\.py) b/\1\n', lines[index])
            if not m or m.group(1) not in FILES:
                raise ScopeError('Unexpected diff path or metadata')
            index += 1
            if index < len(lines) and re.fullmatch(r'index [0-9a-f]+\.\.[0-9a-f]+(?: 100644)?\n', lines[index]):
                index += 1
        if index + 1 >= len(lines):
            raise ScopeError('Truncated diff header')
        m = re.fullmatch(r'--- a/([a-z_]+\.py)\n', lines[index])
        if not m or m.group(1) not in FILES:
            raise ScopeError('Only exact excerpt paths are permitted')
        name = m.group(1)
        if lines[index + 1] != f'+++ b/{name}\n' or name in changed:
            raise ScopeError('Rename, duplicate or unexpected destination')
        changed.add(name)
        index += 2
        old, output, cursor, hunks = sources[name].decode('utf-8').splitlines(keepends=True), [], 0, 0
        while index < len(lines) and lines[index].startswith('@@ '):
            m = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n', lines[index])
            if not m:
                raise ScopeError('Invalid unified hunk')
            old_start, old_count = int(m[1]), int(m[2] if m[2] is not None else 1)
            new_start, new_count = int(m[3]), int(m[4] if m[4] is not None else 1)
            position = old_start - 1 if old_count else old_start
            if position < cursor or position > len(old):
                raise ScopeError('Overlapping or out-of-range hunk')
            output.extend(old[cursor:position]); cursor = position
            if new_start != len(output) + (1 if new_count else 0):
                raise ScopeError('Inconsistent new hunk position')
            index += 1
            consumed = produced = 0
            while index < len(lines) and consumed <= old_count and produced <= new_count:
                line = lines[index]
                if not line or line[0] not in ' +-':
                    break
                if line.startswith('--- ') and consumed == old_count and produced == new_count:
                    break
                marker, content = line[0], line[1:]
                if marker in ' -':
                    if cursor >= len(old) or old[cursor] != content:
                        raise ScopeError('Hunk context mismatch')
                    cursor += 1; consumed += 1
                if marker in ' +':
                    output.append(content); produced += 1
                index += 1
                if consumed == old_count and produced == new_count:
                    break
            if consumed != old_count or produced != new_count:
                raise ScopeError('Truncated or inconsistent hunk')
            hunks += 1
        if not hunks:
            raise ScopeError('File has no hunks')
        output.extend(old[cursor:])
        sources[name] = ''.join(output).encode('utf-8')
    for name in FILES:
        _review_source(name, originals[name], sources[name])
    applied_hashes = {n: sha(b) for n, b in sources.items()}
    return sources, {'status': 'accepted', 'approved': True,
                     'review': 'conservative syntax and side-effect scope review; container still required',
                     'changed_files': sorted(changed), 'patch_sha256': sha(patch),
                     'applied_source_sha256': applied_hashes, 'source_hashes': applied_hashes}


def _host_env():
    return {k: os.environ[k] for k in ('PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONTEXT') if k in os.environ}


def bounded_command(args, timeout=30, limit=LIMIT):
    """Bound merged output while reading, rather than buffering an unbounded pipe."""
    start = time.monotonic()
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=_host_env())
    output, failure = bytearray(), None
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            if time.monotonic() - start > timeout:
                failure = 'timeout'; proc.kill(); break
            for key, _ in selector.select(timeout=0.1):
                chunk = os.read(key.fd, min(16384, limit + 1 - len(output)))
                if not chunk:
                    selector.unregister(key.fileobj)
                else:
                    output.extend(chunk)
                    if len(output) > limit:
                        failure = 'output_limit'; proc.kill(); break
            if failure:
                break
        proc.wait(timeout=5)
    finally:
        selector.close()
        proc.stdout.close()
        if proc.poll() is None:
            proc.kill(); proc.wait()
    return {'exit_code': proc.returncode, 'failure': failure,
            'output': bytes(output[:limit]).decode('utf-8', errors='replace'),
            'output_sha256': sha(bytes(output[:limit])), 'elapsed_seconds': round(time.monotonic() - start, 3)}


def container_command(image_id, inputs, name, mode, branch='upstream'):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id):
        raise ValueError('Content-addressed image ID required')
    return ['docker', 'run', '--pull', 'never', '--rm', '--name', name,
            '--network', 'none', '--read-only', '--user', '65534:65534',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
            '--pids-limit', '32', '--memory', '256m', '--memory-swap', '256m',
            '--cpus', '1', '--ulimit', 'nofile=64:64', '--ulimit', 'core=0:0',
            '--mount', f'type=bind,src={inputs},dst=/input,readonly',
            '--workdir', '/input', '--entrypoint', '/usr/bin/env', image_id,
            '-i', *[f'{k}={v}' for k, v in CLEAN_ENV.items()],
            '/usr/local/bin/python3', '-I', '-B', '/input/trial/container_worker.py', mode, branch]


def _container(image_id, inputs, mode, branch='upstream'):
    name = 'rb-source-' + uuid.uuid4().hex
    result = bounded_command(container_command(image_id, inputs, name, mode, branch), timeout=25)
    # Killing a Docker client is not sufficient to stop its container.
    cleanup = bounded_command(['docker', 'rm', '-f', name], timeout=10, limit=4096)
    result['cleanup_exit_code'] = cleanup['exit_code']
    try:
        result['data'] = json.loads(result['output']) if result['exit_code'] == 0 and not result['failure'] else None
    except ValueError:
        result['data'] = None
        result['failure'] = 'invalid_worker_json'
    return result


def _write_tree(destination, branches):
    destination.chmod(0o755)
    (destination / 'trial').mkdir(mode=0o755)
    for name in ('run_trial.py', 'metamorphic.py', 'PROTOCOL.json', 'container_worker.py'):
        (destination / 'trial' / name).write_bytes(_read_file(HERE / name))
    for branch, files in branches.items():
        folder = destination / branch
        folder.mkdir(mode=0o755)
        for name, raw in files.items():
            (folder / name).write_bytes(raw)
    for path in destination.rglob('*'):
        path.chmod(0o555 if path.is_dir() else 0o444)


def _writable_tree(destination):
    # Only this disposable tree is modified; never follow any candidate link.
    destination.chmod(0o755)
    for path in destination.rglob('*'):
        if path.is_dir():
            path.chmod(0o755)


def run_suite(image='python:3.11-slim', operator_patch=ROOT / 'model_attempt_01' / 'MODEL_PATCH.diff', direct_patch=None):
    report = {'started_utc': utc(), 'status': 'blocked', 'comparisons': {}, 'candidates': {},
              'configuration': {'network': 'none', 'root_read_only': True, 'input_read_only': True,
                                'user': '65534:65534', 'capabilities': [], 'no_new_privileges': True,
                                'memory_bytes': 268435456, 'cpus': 1, 'pids': 32, 'seconds': 25,
                                'output_limit_bytes': LIMIT, 'environment': CLEAN_ENV,
                                'mounts': ['/input (disposable allowlisted files only, read-only)'],
                                'candidate_execution_on_host': False}, 'blockers': []}
    branches = {b: {n: _read_file(ROOT / b / n) for n in FILES} for b in COMPARATORS}
    for key, patch_path in (('operator_supplied', operator_patch), ('direct_meta', direct_patch)):
        if patch_path is None:
            report['candidates'][key] = {'status': 'missing', 'scope': None, 'protocol': None, 'supplemental': None}
            continue
        try:
            patch = _read_file(Path(patch_path))
            applied, scope = review_patch(patch)
            if key == 'operator_supplied':
                for name in FILES:
                    if applied[name] != _read_file(ROOT / 'model_attempt_01' / name):
                        raise ScopeError('Supplied file differs from applying supplied patch')
            branch = 'candidate_' + key
            branches[branch] = applied
            report['candidates'][key] = {'status': 'reviewed', 'scope': scope, 'patch_sha256': sha(patch),
                                         'protocol': None, 'supplemental': None}
        except (ScopeError, OSError) as exc:
            report['candidates'][key] = {'status': 'rejected', 'scope': {'status': 'rejected', 'approved': False, 'reason': str(exc)},
                                         'protocol': None, 'supplemental': None}
    try:
        inspected = bounded_command(['docker', 'image', 'inspect', image], timeout=15, limit=65536)
        report['image_inspect'] = inspected
        if inspected['exit_code'] != 0 or inspected['failure']:
            report['blockers'].append('Docker runtime or selected local image unavailable; no evaluation executed')
            return report
        metadata = json.loads(inspected['output'])[0]
        image_id = metadata['Id']
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id):
            raise ValueError('Invalid Docker image identity')
        report['image'] = {'id': image_id, 'repo_digests': metadata.get('RepoDigests', [])}
        # Inspect output contains unrelated image environment/config fields;
        # retain identity and exit status, not arbitrary metadata.
        report['image_inspect'] = {k: v for k, v in inspected.items() if k != 'output'}
        with tempfile.TemporaryDirectory(prefix='rb-source-inputs-') as temporary:
            inputs = Path(temporary)
            try:
                _write_tree(inputs, branches)
                report['input_sha256'] = {str(p.relative_to(inputs)): sha(p.read_bytes())
                                           for p in inputs.rglob('*') if p.is_file()}
                probe = _container(image_id, inputs, 'probe')
                report['probe'] = probe
                if probe['exit_code'] != 0 or probe['failure'] or probe['data'] is None or probe['data'].get('isolated') is not True:
                    report['blockers'].append('Benign isolation probe failed; no source evaluation executed')
                    return report
                for branch in branches:
                    execution = _container(image_id, inputs, 'evaluate', branch)
                    data = execution.get('data')
                    entry = {'execution': execution, 'protocol': data.get('protocol') if data else None,
                             'supplemental': data.get('supplemental') if data else None}
                    if branch in COMPARATORS:
                        report['comparisons'][branch] = entry
                    else:
                        key = branch.removeprefix('candidate_')
                        report['candidates'][key].update(entry)
                        passed = bool(data and data.get('protocol', {}).get('all_passed'))
                        report['candidates'][key]['status'] = 'accepted' if passed else 'failed'
                report['comparators_reproduced'] = all(
                    report['comparisons'][b]['protocol'] and report['comparisons'][b]['protocol']['passed'] == score
                    and report['comparisons'][b]['protocol']['total'] == 9
                    for b, score in COMPARATORS.items())
                report['status'] = 'completed' if report['comparators_reproduced'] else 'failed'
            finally:
                _writable_tree(inputs)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        report['blockers'].append('Container evaluation unavailable: ' + type(exc).__name__)
    finally:
        report['finished_utc'] = utc()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='python:3.11-slim')
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--direct-patch', type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Refusing to replace an existing observation')
    result = run_suite(args.image, direct_patch=args.direct_patch)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': result['status'], 'blockers': result['blockers'],
                      'comparators_reproduced': result.get('comparators_reproduced', False),
                      'candidate_status': {k: v['status'] for k, v in result['candidates'].items()}}, indent=2))


if __name__ == '__main__':
    main()
