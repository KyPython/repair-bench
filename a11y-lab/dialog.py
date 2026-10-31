"""Second sealed problem: model chooses a bounded, trusted dialog repair; browser owns verdict."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Any

HERE=Path(__file__).resolve().parent
SCHEMA='repair-bench.dialog-proposal.v1'
OPTIONS=('noop','aria_only','managed_dialog')
MAX_BYTES=2048
ORIGINAL_TAG='<div id="dialog-box" data-repair-target="dialog" hidden>'
HOOK='/* TRUSTED_REPAIR_HOOK */'
ATTRS='role="dialog" aria-modal="true" aria-labelledby="dialog-title"'
TRUSTED_BEHAVIOR="""
  // Trusted implementation template; the model never supplies executable JavaScript.
  const outside=document.getElementById('outside');
  const inside=document.getElementById('inside-link');
  opener.addEventListener('click',()=>{outside.inert=true;closer.focus();});
  closer.addEventListener('click',()=>{outside.inert=false;opener.focus();});
  box.addEventListener('keydown',(event)=>{
    if(event.key==='Escape'){event.preventDefault();closer.click();return;}
    if(event.key==='Tab'){
      const backward=event.shiftKey;
      if(backward && document.activeElement===closer){event.preventDefault();inside.focus();}
      if(!backward && document.activeElement===inside){event.preventDefault();closer.focus();}
    }
  });
"""

def digest(data:bytes)->str: return hashlib.sha256(data).hexdigest()

def source()->str:
    raw=(HERE/'dialog_mouse_only.html').read_bytes()
    seal=json.loads((HERE/'dialog_fixture_seal.json').read_text())
    if digest(raw)!=seal.get('a11y-lab/dialog_mouse_only.html'):
        raise ValueError('SEAL_FAIL: dialog source changed')
    text=raw.decode('utf-8')
    if text.count(ORIGINAL_TAG)!=1 or text.count(HOOK)!=1:
        raise ValueError('BASELINE_FAIL: dialog repair markers missing')
    return text

def parse_proposal(data:bytes)->dict[str,str]:
    if len(data)>MAX_BYTES: raise ValueError('candidate exceeds 2048 byte limit')
    try: proposal=json.loads(data)
    except (ValueError,UnicodeDecodeError) as ex: raise ValueError('candidate must be JSON, not code') from ex
    if type(proposal) is not dict or set(proposal)!={'schema','repair'}:
        raise ValueError('candidate must contain exactly schema and repair')
    if proposal.get('schema')!=SCHEMA or type(proposal.get('repair')) is not str or proposal['repair'] not in OPTIONS:
        raise ValueError('unsupported dialog repair')
    return proposal

def apply_plan(src:str,repair:str)->str:
    if src.count(ORIGINAL_TAG)!=1 or src.count(HOOK)!=1: raise ValueError('dialog baseline changed')
    if repair not in OPTIONS: raise ValueError('unsupported repair')
    if repair=='noop': return src
    modified=src.replace(ORIGINAL_TAG,ORIGINAL_TAG[:-1]+' '+ATTRS+'>',1)
    if repair=='managed_dialog': modified=modified.replace(HOOK,TRUSTED_BEHAVIOR,1)
    return modified

def browser_checks(html:str)->dict[str,bool]:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        configured=os.environ.get('RB_CHROMIUM')
        browser_path=configured or ('/usr/bin/chromium' if Path('/usr/bin/chromium').is_file() else None)
        browser=p.chromium.launch(headless=True,**({'executable_path':browser_path} if browser_path else {}))
        try:
            page=browser.new_page()
            page.set_content(html,wait_until='load')
            checks={}
            dialog=page.locator('#dialog-box')
            checks['initially_closed']=not dialog.is_visible()
            page.locator('#open-dialog').click()
            checks['pointer_opens']=dialog.is_visible()
            page.locator('#close-dialog').click()
            checks['pointer_closes']=not dialog.is_visible()
            page.set_content(html,wait_until='load')
            page.keyboard.press('Tab')
            checks['keyboard_reaches_opener']=page.evaluate('document.activeElement?.id')=='open-dialog'
            page.keyboard.press('Enter')
            checks['keyboard_opens']=dialog.is_visible()
            checks['focus_enters_dialog']=page.evaluate('document.activeElement?.id')=='close-dialog'
            checks['dialog_semantics']=dialog.get_attribute('role')=='dialog' and dialog.get_attribute('aria-modal')=='true' and dialog.get_attribute('aria-labelledby')=='dialog-title'
            checks['background_inert']=page.locator('#outside').evaluate('(el)=>el.inert===true')
            page.keyboard.press('Tab')
            checks['tab_reaches_second_control']=page.evaluate('document.activeElement?.id')=='inside-link'
            page.keyboard.press('Tab')
            checks['tab_wraps_to_first_control']=page.evaluate('document.activeElement?.id')=='close-dialog'
            page.keyboard.press('Escape')
            checks['escape_closes']=not dialog.is_visible()
            checks['focus_returns_after_escape']=page.evaluate('document.activeElement?.id')=='open-dialog'
            checks['background_unlocked_after_close']=page.locator('#outside').evaluate('(el)=>el.inert===false')
            return checks
        finally: browser.close()

def evaluate_bytes(data:bytes)->dict[str,Any]:
    candidate=parse_proposal(data)
    src=source()
    checks=browser_checks(apply_plan(src,candidate['repair']))
    return {'kind':'Repair Bench controlled dialog benchmark','task':'dialog','author':'GPT-6 2026-10-28',
            'candidate_sha256':digest(data),'fixture_sha256':digest(src.encode()),
            'repair_type':candidate['repair'],'real_model_inference':False,'candidate_code_execution':False,
            'acceptance':'ACCEPTED' if all(checks.values()) else 'REJECTED','checks':checks,
            'limitations':'Synthetic dialog, one browser, scripted trusted transformations, not a screen-reader or WCAG conformance certification.'}

def prompt()->str:
    return ('Choose one constrained repair for a synthetic settings dialog. A mouse can open/close the dialog, '
            'but opening fails to move keyboard focus inside; Tab can escape into the background; Escape cannot dismiss. '
            'The dialog must have a programmatic name and modality; preserve pointer behavior. '
            'Return ONLY JSON with keys schema (repair-bench.dialog-proposal.v1) and '
            'repair (one of noop, aria_only, managed_dialog), no code or markdown. Source:\n'+source())
