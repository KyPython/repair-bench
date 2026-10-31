"""Fail-closed, locally supplied Meta trial receipt presentation.

Reading a JSON file is NEVER proof that Meta issued it. Public/UI language must
identify the file as operator supplied, and browser rechecks are independent.
This module never makes provider API calls or accepts browser-uploaded receipts.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

ALLOWED = {'menu':{'noop', 'aria_only', 'native_button'},'dialog':{'noop','aria_only','managed_dialog'}}
SHA = set('0123456789abcdef')


def _hexhash(value):
    return type(value) is str and len(value) == 64 and set(value) <= SHA


def load_receipt() -> dict:
    configured = os.environ.get('RB_META_TRIAL_RECEIPT')
    if not configured:
        return {'status': 'NOT_RECORDED', 'is_authenticated_by_app': False}
    target = Path(configured).expanduser()
    try:
        if not target.is_file() or target.stat().st_size > 40000:
            raise ValueError('missing or oversized receipt')
        raw = target.read_bytes()
        doc = json.loads(raw)
        if type(doc) is not dict:
            raise ValueError('wrong receipt')
        task=doc.get('task','menu')
        if task not in ALLOWED or doc.get('kind') != ('repair-bench.a11y.muse-trial.v1' if task=='menu' else 'repair-bench.dialog.muse-trial.v1'):
            raise ValueError('wrong receipt type')
        if doc.get('provider') != 'Meta Model API' or doc.get('model') != 'muse-spark-1.3':
            raise ValueError('wrong provider/model')
        if not _hexhash(doc.get('request_sha256')):
            raise ValueError('missing request fingerprint')
        candidate = doc.get('candidate')
        if type(candidate) is not dict or set(candidate) != {'schema','repair'}:
            raise ValueError('invalid candidate schema')
        if candidate.get('schema') != ('repair-bench.a11y-proposal.v1' if task=='menu' else 'repair-bench.dialog-proposal.v1') or candidate.get('repair') not in ALLOWED[task]:
            raise ValueError('invalid model choice')
        reported = doc.get('verification')
        if type(reported) is not dict or reported.get('real_model_inference') is not True:
            raise ValueError('not a claimed direct model run')
        if reported.get('repair_type') != candidate['repair'] or reported.get('acceptance') not in {'ACCEPTED','REJECTED'}:
            raise ValueError('receipt inconsistent')
        ident = doc.get('provider_identity')
        if type(ident) is not dict or not _hexhash(ident.get('raw_response_sha256')):
            raise ValueError('missing raw-response fingerprint')
        # Still no independent authentication: hashes/response ids inside a JSON
        # file could be fabricated. Only the operator's provider dashboard can
        # confirm usage. We deliberately do not set any 'verified_live' flag.
        return {
            'status': 'OPERATOR_RECEIPT_PRESENT_UNVERIFIED',
            'is_authenticated_by_app': False,
            'label': 'Operator-supplied, not independently provider-authenticated',
            'model': 'muse-spark-1.3',
            'task': task,
            'repair': candidate['repair'],
            'claimed_verdict': reported['acceptance'],
            'request_sha256': doc['request_sha256'],
            'response_sha256': ident['raw_response_sha256'],
            'response_id_present': type(ident.get('response_id')) is str and bool(ident.get('response_id')),
            'file_sha256': hashlib.sha256(raw).hexdigest(),
        }
    except (OSError, ValueError, TypeError, UnicodeDecodeError):
        return {'status': 'INVALID_RECEIPT', 'is_authenticated_by_app': False, 'error':'Receipt failed validation; no model claim permitted'}
