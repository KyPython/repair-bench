#!/usr/bin/env python3
"""Make disposable trusted source-patch controls; preserve upstream exact snippets."""
from pathlib import Path
import difflib

ROOT = Path(__file__).resolve().parent.parent
original = {p.name:p.read_text() for p in (ROOT/'upstream').glob('*.py')}
original_convert=original['convert_response.py']
original_details=original['responses_stop_details.py']

stop_fragment = '    if has_tool_calls:\n        stop_reason = "tool_calls"\n'
stop_corrected = '    if has_tool_calls and response.incomplete_details is None:\n        stop_reason = "tool_calls"\n'
assert original_convert.count(stop_fragment)==1
message_fragment='            tool_calls=tool_calls if len(tool_calls) > 0 else None,\n'
message_corrected='            tool_calls=(tool_calls if len(tool_calls) > 0 and response.incomplete_details is None else None),\n'
assert original_convert.count(message_fragment)==1
explanation_fragment='        explanation=explanation,\n'
explanation_corrected='        explanation=explanation or ("Response incomplete: content_filter" if is_content_filter else None),\n'
assert original_details.count(explanation_fragment)==1

variants={
  'reference': [stop_fragment, message_fragment, explanation_fragment],
  'cosmetic': [None, None, explanation_fragment],
  'stoponly': [stop_fragment, None, None],
  'toolsonly': [None, message_fragment, None],
}
for variant,(fix_stop,fix_message,fix_details) in variants.items():
  dest=ROOT/variant; dest.mkdir(exist_ok=True)
  conv=original_convert; det=original_details
  if fix_stop: conv=conv.replace(fix_stop,stop_corrected)
  if fix_message: conv=conv.replace(fix_message,message_corrected)
  if fix_details: det=det.replace(fix_details,explanation_corrected)
  for name,content in original.items():
    (dest/name).write_text({'convert_response.py':conv,'responses_stop_details.py':det}.get(name,content))
  print(variant, 'changed',sum((dest/name).read_text()!=text for name,text in original.items()))

reference=[]
for name,source in original.items():
    new=(ROOT/'reference'/name).read_text()
    reference+=list(difflib.unified_diff(source.splitlines(True),new.splitlines(True),fromfile=f'a/{name}',tofile=f'b/{name}'))
(ROOT/'reference'/'LOCAL_REFERENCE_PATCH.diff').write_text(''.join(reference))
