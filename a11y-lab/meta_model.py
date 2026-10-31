#!/usr/bin/env python3
"""Optional Meta adapter — GPT-6 2026-10-28. DRY RUN ONLY unless manually authorized.

Never runs from tests. Live mode requires explicit switch and environment key.
No retries, no other tools or agents, no source changes, no claim credits applied.
"""
import json
import os
import sys
import urllib.request
from evaluate import prompt, parse_proposal

URL='https://api.meta.ai/v1/chat/completions'
MODEL='muse-spark-1.3'


def request_body():
    return {'model':MODEL, 'messages':[
        {'role':'developer','content':'Return only the exact JSON schema requested. Do not write executable code.'},
        {'role':'user','content':prompt()}], 'max_completion_tokens':256}


def main(args):
    if args == ['--dry-run']:
        print(json.dumps({'url': URL, 'request':request_body(), 'billing_verified':False, 'api_call_made':False},indent=2)); return 0
    if args != ['--live','--i-approve-billable-inference']:
        print('Default is offline. Use --dry-run. Live requires separate, explicit per-run authorization and credit checks.', file=sys.stderr);return 64
    key=os.environ.get('MODEL_API_KEY')
    if not key:
        print('MODEL_API_KEY missing. No call made.',file=sys.stderr);return 2
    body=json.dumps(request_body()).encode()
    req=urllib.request.Request(URL,data=body,method='POST',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as res:
            raw=res.read(200_000)
        data=json.loads(raw)
        if data.get('model') not in (MODEL,):
            raise ValueError('Provider model identity mismatch')
        choices=data.get('choices',[])
        if len(choices)!=1 or choices[0].get('finish_reason')!='stop':
            raise ValueError('Not one completed reply')
        reply=choices[0].get('message',{}).get('content')
        if type(reply) is not str:raise ValueError('Non-text reply')
        plan=parse_proposal(reply.encode())
        # Model output recorded as a candidate only, not applied to source.
        print(json.dumps({'model':MODEL,'model_reply':plan,'provider_response_id':data.get('id'), 'usage':data.get('usage'), 'evaluated':False},indent=2))
        return 0
    except Exception as e:
        print(f'No valid candidate received: {type(e).__name__}',file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main(sys.argv[1:]))
