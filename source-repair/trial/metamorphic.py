#!/usr/bin/env python3
"""Supplemental varied-input safety checks. Post-reference; NOT preregistered."""
import hashlib
import json
from pathlib import Path
from run_trial import ROOT, Logger, OpenAIResponse, IncompleteDetails, FunctionCall, ResponseOutputMessage, ResponseOutputRefusal, compile_pinned_source


def run(branch):
    f, hashes = compile_pinned_source(ROOT/branch, require_original=branch=='upstream')
    cases=[]
    for reason in [None,'content_filter','max_output_tokens']:
        for count in [0,1,2]:
            for refusal in [False,True]:
                label=f"reason={reason or 'completed'}; calls={count}; refusal={refusal}"
                items=[FunctionCall(name=f'fn{i}') for i in range(count)]
                if refusal: items.append(ResponseOutputMessage([ResponseOutputRefusal('Refusal!')]))
                response=OpenAIResponse('mock',IncompleteDetails(reason) if reason else None,items)
                msg,stop,_=f['_chat_message_assistant_from_openai_response']('mock',response,[])
                details=f['collect_stop_details']('inspect',Logger(),lambda: f['responses_stop_details'](response))
                if reason=='content_filter':
                    expected=("content_filter",False,"content_filter",True)
                elif reason=='max_output_tokens':
                    expected=("max_tokens",False,'refusal' if refusal else None,bool(refusal))
                elif count:
                    expected=("tool_calls",True,'refusal' if refusal else None,bool(refusal))
                else:
                    expected=("stop",False,'refusal' if refusal else None,bool(refusal))
                observed=(stop,bool(msg.tool_calls),details.type if details else None,bool(details and details.explanation))
                cases.append({'scenario':label,'pass':expected==observed,'expected':expected,'observed':observed})
    return {'branch':branch,'checks':len(cases),'passed':sum(c['pass'] for c in cases),'results':cases}

if __name__=='__main__':
    out={branch:run(branch) for branch in ['upstream','reference','cosmetic','stoponly','toolsonly']}
    path=ROOT/'results'/'supplemental_metamorphic.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print([(branch,result['passed'],result['checks']) for branch,result in out.items()]);print('sha256',hashlib.sha256(path.read_bytes()).hexdigest())
