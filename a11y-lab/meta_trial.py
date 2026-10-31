#!/usr/bin/env python3
"""One-shot Muse Spark trial + independent browser verification.

GPT-6 draft, 2026-10-28. No network unless all live switches and local key
are present. Output candidate is a *bounded declarative choice*, never code.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request
from typing import Any

from evaluate import evaluate_bytes, prompt, source
from dialog import evaluate_bytes as dialog_evaluate, prompt as dialog_prompt, source as dialog_source

URL = 'https://api.meta.ai/v1/chat/completions'
MODEL = 'muse-spark-1.3'
MAX_RESPONSE_BYTES = 200_000


def request_payload(task: str = 'menu') -> dict[str, Any]:
    if task not in ('menu','dialog'): raise ValueError('unsupported task')
    return {
        'model': MODEL,
        'messages': [
            {'role': 'developer', 'content': 'Return only the requested JSON schema; no markdown and no executable code.'},
            {'role': 'user', 'content': prompt() if task == 'menu' else dialog_prompt()},
        ],
        'max_completion_tokens': 2048,
        'reasoning_effort': 'low',
        'response_format': {'type':'json_object'},
        'store': False,
    }


def parse_provider_response(data: bytes, task: str = 'menu') -> tuple[dict[str, str], dict[str, Any]]:
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError('provider response too large')
    response = json.loads(data)
    if type(response) is not dict or response.get('model') != MODEL:
        raise ValueError('provider model identity missing or mismatched')
    choices = response.get('choices')
    if type(choices) is not list or len(choices) != 1:
        raise ValueError('expected exactly one provider choice')
    choice = choices[0]
    if type(choice) is not dict or choice.get('finish_reason') != 'stop':
        raise ValueError('provider completion truncated or not stopped')
    message = choice.get('message')
    if type(message) is not dict or type(message.get('content')) is not str:
        raise ValueError('provider completion not a string')
    from evaluate import parse_proposal as menu_parse
    from dialog import parse_proposal as dialog_parse
    if task not in ('menu','dialog'): raise ValueError('unsupported task')
    content = message['content']
    candidate = (menu_parse if task=='menu' else dialog_parse)(content.encode('utf-8'))
    # No untrusted output may be executed; the evaluator transforms a trusted fixture.
    identity = {
        'response_id': sanitized_response(data).get('id'),
        'usage': sanitized_response(data).get('usage'),
        'raw_response_sha256': hashlib.sha256(data).hexdigest(),
    }
    return candidate, identity


def preflight_oracle(task: str = 'menu') -> None:
    """Ensure local browser and sealed fixtures work *before* a billable request."""
    if task=='menu':
        source()
        variants=[('noop','REJECTED'),('native_button','ACCEPTED')]
        schema='repair-bench.a11y-proposal.v1'
        evaluator=evaluate_bytes
    elif task=='dialog':
        dialog_source()
        variants=[('noop','REJECTED'),('managed_dialog','ACCEPTED')]
        schema='repair-bench.dialog-proposal.v1'
        evaluator=dialog_evaluate
    else: raise ValueError('unsupported task')
    for repair, expected in variants:
        candidate = {'schema':schema,'repair':repair}
        verdict = evaluator(json.dumps(candidate).encode())['acceptance']
        if verdict != expected:
            raise RuntimeError('Local acceptance oracle preflight failed; no API call made')


class AttemptJournal:
    """Append-only, fsynced sanitized evidence. No response content or secrets."""
    def __init__(self, path: Path, fingerprint: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        # Request-specific reservation survives failure and blocks accidental resend.
        self.lock = path.parent / ('.request-' + fingerprint + '.reserved')
        with self.lock.open('x', encoding='utf-8') as f:
            f.write(str(path.name)); f.flush(); os.fsync(f.fileno())
        self.handle = path.open('x', encoding='utf-8')
        self.append('RESERVED', request_sha256=fingerprint, network_attempted=False)

    def append(self, state: str, **safe):
        self.handle.write(json.dumps({'state':state,'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),**safe},sort_keys=True)+'\n')
        self.handle.flush(); os.fsync(self.handle.fileno())

    def close(self):
        self.handle.close()


def sanitized_response(raw: bytes) -> dict[str, Any]:
    """Hashes raw bytes but never persists content/reasoning/arbitrary provider fields."""
    out = {'raw_response_sha256':hashlib.sha256(raw).hexdigest(),'response_bytes':len(raw)}
    try:
        doc=json.loads(raw)
        if type(doc) is not dict: return out
        for name in ('id','model'):
            value=doc.get(name)
            # Restrict metadata strings, never copy unbounded provider text.
            if type(value) is str and len(value)<=160 and all(c.isalnum() or c in '-_.:/' for c in value): out[name]=value
        usage=doc.get('usage')
        if type(usage) is dict:
            out['usage']={k:v for k,v in usage.items() if k in ('prompt_tokens','completion_tokens','total_tokens') and type(v) is int and v>=0}
        choices=doc.get('choices')
        if type(choices) is list and len(choices)==1 and type(choices[0]) is dict:
            finish=choices[0].get('finish_reason')
            if finish in ('stop','length','tool_calls','content_filter'):out['finish_reason']=finish
    except (ValueError,UnicodeDecodeError):pass
    return out


def trial_once(task: str = 'menu', journal_path: Path | None = None) -> dict[str, Any]:
    key = os.environ.get('MODEL_API_KEY')
    if not key: raise RuntimeError('MODEL_API_KEY not configured: no API call made')
    if journal_path is None: raise RuntimeError('Durable journal required: no API call made')
    preflight_oracle(task)
    request=request_payload(task)
    serialized=json.dumps(request,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    fingerprint=hashlib.sha256(serialized).hexdigest()
    journal=AttemptJournal(Path(journal_path),fingerprint)
    try:
        http_req=urllib.request.Request(URL,data=serialized,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
        # Persist BEFORE transport. Any interruption from here means UNKNOWN, never retry.
        journal.append('NETWORK_ATTEMPTED',network_attempted=True,task=task,model=MODEL)
        with urllib.request.urlopen(http_req,timeout=45) as response:
            raw=response.read(MAX_RESPONSE_BYTES+1)
        journal.append('RESPONSE_RECEIVED',**sanitized_response(raw))
        candidate,identity=parse_provider_response(raw,task)
        journal.append('CANDIDATE_PARSED',candidate=candidate)
        evaluator=evaluate_bytes if task=='menu' else dialog_evaluate
        result=evaluator(json.dumps(candidate,separators=(',',':')).encode('utf-8'))
        result['real_model_inference']=True
        journal.append('EVALUATED',acceptance=result['acceptance'],checks=result['checks'])
        return {'kind':'repair-bench.a11y.muse-trial.v1' if task=='menu' else 'repair-bench.dialog.muse-trial.v1',
                'task':task,'author_of_runner':'GPT-6 base; Instinct private safeguard patch 2026-10-28',
                'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'provider':'Meta Model API',
                'model':MODEL,'provider_identity':identity,'request_sha256':fingerprint,'candidate':candidate,
                'verification':result,'attempt_journal':str(journal_path),
                'note':'One source-only three-option synthetic choice; independent browser verification. Not general code repair or WCAG conformance.'}
    except Exception as ex:
        try:journal.append('UNKNOWN_NO_RETRY',error_type=type(ex).__name__)
        except OSError:pass # Earlier fsynced NETWORK_ATTEMPTED/RESPONSE remains evidence.
        raise
    finally:journal.close()

def main(args: list[str]) -> int:
    task='menu'
    if args[-2:] == ['--task','dialog']:
        task='dialog'
        args=args[:-2]
    if args == ['--dry-run']:
        payload = request_payload(task)
        # No key or personally identifying data.
        print(json.dumps({
            'request_url': URL, 'model': MODEL, 'task':task,
            'request_sha256': hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest(),
            'api_call_made': False, 'provider_identity': None,
            'candidate_evaluated': False,
            'authorization_state': 'not_checked',
        }, indent=2))
        return 0
    if len(args) != 4 or args[:3] != ['--live', '--credits-confirmed', '--approve-one-call']:
        print('Refusing network. Use --dry-run; live needs --live --credits-confirmed --approve-one-call RECEIPT_PATH.', file=sys.stderr)
        return 64
    receipt_path = Path(args[3])
    if receipt_path.exists():
        print('Receipt already exists; refusing overwrite.', file=sys.stderr)
        return 64
    if not os.environ.get('MODEL_API_KEY'):
        print('MODEL_API_KEY is missing; zero API calls made.', file=sys.stderr)
        return 2
    try:
        result = trial_once(task, receipt_path.with_suffix(receipt_path.suffix+'.attempt.jsonl'))
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        # exclusive creation prevents clobber, including another agent receipt.
        with receipt_path.open('x', encoding='utf-8') as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write('\n')
        print(json.dumps({
            'receipt': str(receipt_path),
            'model': MODEL, 'task': task,
            'acceptance': result['verification']['acceptance'],
            'provider_response_id': result['provider_identity']['response_id'],
            'real_model_inference': True,
            'warning': 'Billing is not verified by this program; credit confirmation flag is a human assertion.',
        }, indent=2))
        return 0 if result['verification']['acceptance'] == 'ACCEPTED' else 2
    except Exception as ex:
        # Never log the credential, prompt-bearing HTTP error body or raw model reasoning.
        print(f'Trial failed: {type(ex).__name__}. Retain attempt journal/reservation; outcome UNKNOWN, NO RETRY. Check provider account before further action.', file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
