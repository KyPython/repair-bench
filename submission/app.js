'use strict';
const $ = (id) => document.getElementById(id);
const modes={
 menu:{schema:'repair-bench.a11y-proposal.v1',title:'The keyboard trap',description:'ARIA cannot make a click-only menu keyboard accessible.',options:[['noop','Leave it as-is','Mouse works. Keyboard users are locked out.','BASELINE'],['aria_only','ARIA + tab index','Looks accessible; Enter still fails.','FALSE GREEN'],['native_button','Native button repair','Mouse, Enter and Space all activate.','VALID REPAIR']],checks:['initially_closed','mouse_opens','mouse_closes','keyboard_reaches_trigger','enter_activates','focus_restored','space_activates','semantic_button','accessible_name']},
 dialog:{schema:'repair-bench.dialog-proposal.v1',title:'The modal focus trap',description:'ARIA alone cannot manage focus, Escape or keyboard containment.',options:[['noop','Leave it as-is','Pointer works. Keyboard and Escape are broken.','BASELINE'],['aria_only','ARIA-only dialog','Named and modal, but focus handling remains broken.','FALSE GREEN'],['managed_dialog','Managed dialog','Focus enters, Tab is contained and Escape restores focus.','VALID REPAIR']],checks:['initially_closed','pointer_opens','pointer_closes','keyboard_reaches_opener','keyboard_opens','focus_enters_dialog','dialog_semantics','background_inert','tab_reaches_second_control','tab_wraps_to_first_control','escape_closes','focus_returns_after_escape','background_unlocked_after_close']}
};
let task='menu';
const nameOf=(repair)=>modes[task].options.find(v=>v[0]===repair)?.[1]||repair;

const checks=()=>modes[task].checks;
const labels = {pointer_opens:'Pointer opens',pointer_closes:'Pointer closes',keyboard_reaches_opener:'Keyboard reaches opener',keyboard_opens:'Enter opens',focus_enters_dialog:'Focus enters dialog',dialog_semantics:'Named dialog semantics',background_inert:'Background inert',tab_reaches_second_control:'Tab reaches dialog control',tab_wraps_to_first_control:'Tab wraps inside',escape_closes:'Escape dismisses',focus_returns_after_escape:'Focus returns after Escape',background_unlocked_after_close:'Background unlocked',initially_closed:'Panel starts closed',mouse_opens:'Pointer opens',mouse_closes:'Pointer closes',keyboard_reaches_trigger:'Keyboard reaches trigger',enter_activates:'Enter activates',focus_restored:'Focus returns',space_activates:'Space activates',semantic_button:'Native button semantics',accessible_name:'Accessible name present'};
let busy=false;
function selected(){return document.querySelector('input[name="repair"]:checked').value;}
function updateSelection(){const repair=selected();document.querySelectorAll('.choice').forEach(el=>el.classList.toggle('selected',el.querySelector('input').checked));$('fixture').src=`/api/fixture?task=${task}&repair=${encodeURIComponent(repair)}`;$('verdict').className='verdict notrun';$('verdict').textContent='NOT YET RUN';$('checks').replaceChildren();let p=document.createElement('p');p.className='placeholder';p.textContent='This candidate has not been tested in the current run.';$('checks').appendChild(p);$('resultSub').textContent=`Ready to evaluate: ${nameOf(repair)}.`;}
function render(result){$('verdict').textContent=result.acceptance;$('verdict').className=`verdict ${result.acceptance.toLowerCase()}`;$('resultSub').textContent=`Actual Chromium audit of ${nameOf(result.repair_type)}. No model call was made.`;let nodes=[];for(const key of checks()){const pass=result.checks[key]===true;const node=document.createElement('div');node.className=`check ${pass?'pass':'fail'}`;const status=document.createElement('b');status.textContent=pass?'PASS ✓':'FAIL ×';const title=document.createElement('span');title.textContent=labels[key];node.append(status,title);nodes.push(node);}$('checks').replaceChildren(...nodes);}
function setBusy(value){busy=value;$('verify').disabled=value;$('all').disabled=value;$('taskMenu').disabled=value;$('taskDialog').disabled=value;document.querySelectorAll('input[name="repair"]').forEach(el=>el.disabled=value);}
async function audit(repair){const res=await fetch('/api/evaluate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task,schema:modes[task].schema,repair})});const data=await res.json();if(!res.ok){throw Error(data.error||'Verification unavailable');}if(data.task!==task||data.run_provenance!=='LOCAL_CHROMIUM_OFFLINE'||data.real_model_inference!==false){throw Error('Invalid response provenance');}return data;}
async function runOne(){if(busy)return;setBusy(true);$('compare').hidden=true;$('progress').textContent='Running actual Chromium browser assertions…';try{let result=await audit(selected());render(result);$('progress').textContent=`${result.acceptance}: ${Object.values(result.checks).filter(Boolean).length} of ${Object.keys(result.checks).length} assertions passed.`;}catch(ex){$('progress').textContent=`Verification unavailable: ${ex.message}`;$('verdict').textContent='ERROR';}finally{setBusy(false);}}
async function runAll(){if(busy)return;setBusy(true);$('compare').hidden=true;const results=[];try{for(const [repair] of modes[task].options){$('progress').textContent=`Verifying ${nameOf(repair)} in Chromium…`;results.push(await audit(repair));}const area=$('compareGrid');area.replaceChildren();for(const result of results){const item=document.createElement('div');item.className='compare-item';const name=document.createElement('b');name.textContent=nameOf(result.repair_type);const status=document.createElement('span');status.className=result.acceptance==='ACCEPTED'?'yes':'no';status.textContent=`${result.acceptance} · ${Object.values(result.checks).filter(Boolean).length}/${Object.keys(result.checks).length} passed`;item.append(name,status);area.appendChild(item);}$('compare').hidden=false;render(results.find(x=>x.repair_type===selected()));const expected=results.map(x=>x.acceptance).join(',');$('progress').textContent=expected==='REJECTED,REJECTED,ACCEPTED'?'Complete: two rejected, one accepted — independent offline Chromium verification.':`Unexpected verification outcome (${expected}); inspect the individual checks before drawing conclusions.`;}catch(ex){$('progress').textContent=`Audit interrupted: ${ex.message}`;$('compare').hidden=true;}finally{setBusy(false);}}
async function loadModelReceipt(){
  try {
    const res=await fetch('/api/model-receipt',{cache:'no-store'});
    if(!res.ok)throw Error('Receipt unavailable');
    const info=await res.json();
    if(info.status==='OPERATOR_RECEIPT_PRESENT_UNVERIFIED'){
      $('modelReceiptTitle').textContent='Operator-supplied Meta trial receipt';
      $('modelExplain').textContent='A locally supplied trial JSON file claims a Muse Spark result. This UI does not authenticate it against Meta or make any model call. Independently review the provider account receipt before calling it a real model result.';
      $('modelReceiptStatus').textContent='RECEIPT UNVERIFIED';
      $('modelReceiptInfo').textContent=`Recorded ${info.task||'menu'} choice: ${modes[info.task||'menu']?.options.find(x=>x[0]===info.repair)?.[1]}; reported verdict: ${info.claimed_verdict}. Model: ${info.model}. This JSON file is NOT independently authenticated against Meta's billing dashboard; verify the response before making any live-model claims.`;
      const verify=$('verifyModelReceipt');verify.hidden=false;verify.addEventListener('click',async()=>{
        switchTask(info.task||'menu');const radio=document.querySelector(`input[name="repair"][value="${info.repair}"]`);
        if(!radio)return;radio.checked=true;updateSelection();await runOne();
        $('resultSub').textContent=`Chromium evaluation of operator-provided ${info.model} choice. The Meta account receipt remains independently unverified.`;
      });
    }else if(info.status==='INVALID_RECEIPT'){
      $('modelReceiptTitle').textContent='Trial receipt rejected';
      $('modelExplain').textContent='The operator-supplied JSON failed schema/provenance checks. The independent browser verifier remains usable offline.';
      $('modelReceiptStatus').textContent='INVALID RECEIPT';
      $('modelReceiptInfo').textContent='Operator receipt failed validation. No real Meta inference is claimed.';
    }
  }catch(_){$('modelReceiptInfo').textContent='Model receipt unavailable; offline verifier only.';}
}
function switchTask(mode){
 if(busy||!modes[mode])return;
 task=mode;const m=modes[mode];$('workspaceTitle').textContent=m.title;$('taskDescription').textContent=m.description;$('fixtureUrl').textContent=`sealed-fixture.local/${mode}`;
 for(const n of ['menu','dialog']){const b=$(n==='menu'?'taskMenu':'taskDialog');b.classList.toggle('active',n===mode);b.setAttribute('aria-pressed',String(n===mode));}
 document.querySelectorAll('.choice').forEach((el,i)=>{const [value,title,desc,tag]=m.options[i];const input=el.querySelector('input');input.value=value;input.checked=i===0;el.querySelector('strong').textContent=title;el.querySelector('small').textContent=desc;el.querySelector('.choice-tag').textContent=tag;});
 $('compare').hidden=true;$('progress').textContent='Ready for independent behavioral verification.';updateSelection();
}
async function init(){switchTask('menu');$('taskMenu').addEventListener('click',()=>switchTask('menu'));$('taskDialog').addEventListener('click',()=>switchTask('dialog'));loadModelReceipt();for(const input of document.querySelectorAll('input[name="repair"]'))input.addEventListener('change',updateSelection);$('verify').addEventListener('click',runOne);$('all').addEventListener('click',runAll);try{const res=await fetch('/api/status');if(!res.ok)throw Error('Sealed fixture unavailable');const status=await res.json();if(status.ready!==true||status.billing!=='none')throw Error('Unexpected runtime configuration');if(!Array.isArray(status.benchmarks)||status.benchmarks.length!==2)throw Error('Missing second benchmark');$('sourceHash').textContent=`MENU ${status.source_sha256.slice(0,12)}… · DIALOG ${status.dialog_source_sha256.slice(0,12)}…`;}catch(ex){$('sourceHash').textContent='Sealed source unavailable';$('progress').textContent='Cannot verify sealed source. Stop.';$('verify').disabled=true;$('all').disabled=true;}}
init();
