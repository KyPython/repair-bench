#!/usr/bin/env python3
"""Build an offline, source-aware repair prompt. No HTTP/client/model execution.

Model output must be treated as untrusted. Run returned code ONLY in a real
network-denied, secret-free, separate sandbox — never in this process.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

PROMPT = '''You are investigating a documented regression in a Python AI-evaluation library. You must propose a SOURCE PATCH, not select a predefined repair. You have ONE attempt; do not claim a test passed or invent tool results. Do not change interfaces unnecessarily.

Observed: A response interrupted by content filtering after beginning a tool call is converted to stop_reason="tool_calls" with no visible stop_details; a downstream agent could execute the partial call. Ordinary completed tool-call responses must continue to work. Distinguish stop_reason, stop_details and tool_calls: these can be separate control paths.

Allowed file edits: source snippets corresponding to model/_openai_responses.py (both functions in file) and model/_model_output.py (collector). Preserve all unrelated behavior. Do not edit test code. Return JSON only with keys diagnosis, patch (a unified diff applying to the supplied source snippets, with paths exactly as supplied), risks, tests_to_run. Do not supply code fences. The patch will be MANUALLY inspected and run only in a separate restricted sandbox; this prompt does not authorize code execution.

### ORIGINAL PINNED SOURCE
'''

def get_payload() -> dict:
    source_names = ['convert_response.py','responses_stop_details.py','collect_stop_details.py']
    material = '\n\n'.join('### file: '+n+'\n'+(ROOT/'upstream'/n).read_text() for n in source_names)
    return dict(model='muse-spark-1.3',mode='standard',tools=[],web_search=False,temperature=0,attempt_limit=1,
                output_schema={'type':'object','required':['diagnosis','patch','risks','tests_to_run']},
                prompt=PROMPT+material,
                provenance='PROPOSAL_ONLY_NOT_EXECUTABLE',metadata={'source_ref':'386e099', 'sample':'inspect_ai content-filter/tool-call conflict'})

if __name__=='__main__':
    p=get_payload()
    b=json.dumps(p,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    print(json.dumps({'dry_run':True,'api_call_made':False,'provider_receipt':None,
        'candidate_evaluated':False,'requires_owner_spend_review':True,
        'prompt_sha256':hashlib.sha256(p['prompt'].encode()).hexdigest(),
        'request_sha256':hashlib.sha256(b).hexdigest(),
        'input_bytes':len(b),'model':p['model'],'mode':p['mode'],'tool_count':0},indent=2))
