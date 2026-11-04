"""Read-only, allowlisted source-repair evidence. Never imports candidate code.

This local file is a replay artifact, not provider authentication. The fixed
path is intentionally independent of query strings and environment variables.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

EVIDENCE = Path(__file__).resolve().parents[1] / 'source-repair' / 'model-trial.json'
BRANCHES = ('upstream', 'reference', 'cosmetic', 'stoponly', 'toolsonly')
CANDIDATES = ('operator_supplied', 'direct_meta', 'direct_meta_02')
STATUSES = {'blocked', 'failed', 'completed', 'accepted', 'rejected', 'not_run', 'unavailable'}
TRANSPORT_STATUSES = STATUSES | {'reserved', 'not_sent', 'uncertain'}
CASES = ('filtered_tool', 'filtered_tool_with_refusal', 'filtered_no_tool',
         'truncated_tool', 'truncated_no_tool', 'normal_tool', 'normal_text',
         'normal_refusal', 'truncated_tool_with_refusal')
SECRET = re.compile(r'(?i)(?:bearer\s+\S+|\b(?:sk|mapi)[-_][A-Za-z0-9_-]{12,}|'
                    r'(?:api[_ -]?key|access[_ -]?token|authorization|password)\s*[:=]\s*\S+)')


def _text(value, maximum=2000):
    if type(value) is not str or len(value) > maximum or SECRET.search(value):
        raise ValueError('Invalid public text')
    return value


def _texts(value):
    if type(value) is not list or len(value) > 100:
        raise ValueError('Invalid public text list')
    return [_text(item) for item in value]


def _hash(value):
    if value is None:
        return None
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Invalid hash')
    return value


def _count(value):
    if type(value) is not int or not 0 <= value <= 10**12:
        raise ValueError('Invalid count')
    return value


def _usage(value, depth=0):
    if value is None:
        return None
    if type(value) is not dict or depth > 4 or len(value) > 50:
        raise ValueError('Invalid usage')
    result = {}
    for key, item in value.items():
        # Counters and nested counter groups only. Arbitrary provider text,
        # account identifiers and unrelated private metadata never pass through.
        if not re.fullmatch('[a-z][a-z0-9_]{0,79}', key):
            raise ValueError('Invalid usage key')
        if any(word in key for word in ('secret', 'key', 'token_id', 'account', 'authorization')):
            continue
        result[key] = _usage(item, depth+1) if type(item) is dict else _count(item)
    return result


def _observed(value):
    if type(value) is not dict or type(value.get('dispatch')) is not bool:
        raise ValueError('Invalid observation')
    result = {'dispatch': value['dispatch']}
    for key in ('stop', 'details_type', 'explanation', 'message_text'):
        result[key] = None if value.get(key) is None else _text(value[key])
    result['tool_call_count'] = _count(value.get('tool_call_count', 0))
    return result


def _protocol(value):
    if value is None:
        return None
    if type(value) is not dict or value.get('total') != 9 or type(value.get('cases')) is not list:
        raise ValueError('Invalid protocol result')
    cases = value['cases']
    if len(cases) != 9 or {c.get('case') for c in cases if type(c) is dict} != set(CASES):
        raise ValueError('Invalid case identities')
    rows = []
    for case in cases:
        if type(case.get('passed')) is not bool:
            raise ValueError('Invalid pass value')
        failures = _texts(case.get('failures', []))
        if case['passed'] == bool(failures):
            raise ValueError('Inconsistent failure details')
        rows.append({'case': case['case'], 'passed': case['passed'],
                     'failures': failures, 'observed': _observed(case.get('observed'))})
    passed = sum(row['passed'] for row in rows)
    if type(value.get('passed')) is not int or passed != value['passed']:
        raise ValueError('Inconsistent score')
    if 'all_passed' in value and value['all_passed'] is not (passed == 9):
        raise ValueError('Inconsistent acceptance')
    return {'passed': passed, 'total': 9, 'all_passed': passed == 9,
            'protocol_sha256': _hash(value.get('protocol_sha256')), 'cases': rows}


def _supplemental(value):
    if value is None:
        return None
    if type(value) is not dict or value.get('checks') != 18:
        raise ValueError('Invalid supplemental result')
    passed = _count(value.get('passed'))
    if passed > 18:
        raise ValueError('Invalid supplemental score')
    # Replay the separately labeled aggregate; do not expose arbitrary
    # evaluator output or treat these post-reference checks as acceptance.
    return {'passed': passed, 'checks': 18}


def _scope(value):
    if value is None:
        return None
    if type(value) is not dict:
        raise ValueError('Invalid scope result')
    result = {}
    if 'approved' in value:
        if type(value['approved']) is not bool:
            raise ValueError('Invalid scope approval')
        result['approved'] = value['approved']
    if 'status' in value:
        result['status'] = _text(value['status'], 100)
    if 'reasons' in value:
        result['reasons'] = _texts(value['reasons'])
    return result


def _candidate(value):
    if type(value) is not dict or value.get('status') not in STATUSES:
        raise ValueError('Invalid candidate')
    patch = None if value.get('patch') is None else _text(value['patch'], 100000)
    patch_hash = _hash(value.get('patch_sha256'))
    if patch is not None and hashlib.sha256(patch.encode()).hexdigest() != patch_hash:
        raise ValueError('Patch fingerprint mismatch')
    result = {'status': value['status'], 'provenance': _text(value.get('provenance', '')),
              'patch': patch, 'patch_sha256': patch_hash,
              'protocol': _protocol(value.get('protocol')),
              'supplemental': _supplemental(value.get('supplemental')),
              'scope': _scope(value.get('scope'))}
    if value.get('status') == 'accepted' and (
        not result['protocol'] or not result['protocol']['all_passed'] or
        not result['scope'] or result['scope'].get('approved') is not True
    ):
        raise ValueError('Acceptance requires scope and nine frozen checks')
    statements = value.get('model_statements')
    if statements is not None:
        if type(statements) is not dict:
            raise ValueError('Invalid model statements')
        result['model_statements'] = {'diagnosis': _text(statements.get('diagnosis', '')),
                                     'risks': _texts(statements.get('risks', [])),
                                     'tests_to_run': _texts(statements.get('tests_to_run', []))}
    return result


def _transport(value):
    if type(value) is not dict or value.get('status') not in TRANSPORT_STATUSES:
        raise ValueError('Invalid transport')
    clean = {'status': value['status']}
    for key in ('requested_model', 'returned_model', 'response_id', 'provider_request_id', 'finish_reason',
                'reserved_at_utc', 'sent_at_utc', 'received_at_utc'):
        clean[key] = None if value.get(key) is None else _text(value[key], 200)
    for key in ('request_sha256', 'response_sha256', 'patch_sha256'):
        clean[key] = _hash(value.get(key))
    clean['usage'] = _usage(value.get('usage'))
    return clean


def sanitize(doc):
    if type(doc) is not dict or type(doc.get('schema_version')) is not int or doc['schema_version'] != 1:
        raise ValueError('Invalid evidence schema')
    if doc.get('status') not in {'blocked', 'failed', 'completed'}:
        raise ValueError('Invalid evidence status')
    clean_transport = _transport(doc.get('transport'))
    second = doc.get('transport_02')
    clean_second = None if second is None else _transport(second)
    comparisons = doc.get('comparisons', {})
    candidates = doc.get('candidates', {})
    if type(comparisons) is not dict or type(candidates) is not dict:
        raise ValueError('Invalid comparisons')
    clean_comparisons = {}
    for branch in BRANCHES:
        if branch in comparisons:
            row = comparisons[branch]
            if type(row) is not dict:
                raise ValueError('Invalid comparator')
            clean_comparisons[branch] = {'protocol': _protocol(row.get('protocol')),
                                         'supplemental': _supplemental(row.get('supplemental'))}
    clean_candidates = {name: _candidate(candidates[name]) for name in CANDIDATES if name in candidates}
    audit, validation = doc.get('audit', {}), doc.get('validation', {})
    if type(audit) is not dict or type(validation) is not dict:
        raise ValueError('Invalid evidence notes')
    return {'schema_version': 1, 'status': doc['status'],
            'label': 'Local recorded evidence; the replay does not authenticate the provider',
            'blockers': _texts(doc.get('blockers', [])), 'transport': clean_transport,
            'transport_02': clean_second,
            'comparisons': clean_comparisons, 'candidates': clean_candidates,
            'audit': {'claims': _texts(audit.get('claims', [])),
                      'limitations': _texts(audit.get('limitations', []))},
            'validation': {'observations': _texts(validation.get('observations', []))}}


def load_source_trial():
    try:
        if not EVIDENCE.exists():
            return {'schema_version': 1, 'status': 'missing', 'error': 'No source model trial recorded'}
        if EVIDENCE.is_symlink() or not EVIDENCE.is_file() or EVIDENCE.stat().st_size > 1_000_000:
            raise ValueError('Invalid evidence file')
        return sanitize(json.loads(EVIDENCE.read_bytes()))
    except (OSError, ValueError, TypeError, KeyError, UnicodeDecodeError, RecursionError):
        return {'schema_version': 1, 'status': 'invalid', 'error': 'Source model trial failed validation'}
