'use strict';
const labels={upstream:'The unchanged conversion loses content-filter details and exposes incomplete calls.',cosmetic:'A warning is restored, but the tool call is still available for execution.',stoponly:'The stop reason is improved, but partial calls and missing details remain.',toolsonly:'Partial calls are suppressed, but the stop reason and filter evidence can still be wrong.',reference:'The reference keeps normal calls, hides incomplete ones, and preserves block evidence.'};
const candidateNames={operator_supplied:'Operator-supplied candidate',direct_meta:'Direct Meta candidate',direct_meta_02:'Second direct Meta candidate'};
const byId=id=>document.getElementById(id);
let results=null,trial=null;

function textRow(parent,label,value){
 const row=document.createElement('div');row.className='evidence-row';
 const name=document.createElement('dt');name.textContent=label;
 const detail=document.createElement('dd');detail.textContent=value;
 row.append(name,detail);parent.appendChild(row);
}
function notes(parent,items){
 parent.replaceChildren();
 for(const text of items){const item=document.createElement('li');item.textContent=text;parent.appendChild(item);}
}
function protocolFor(branch){
 if(candidateNames[branch])return trial?.candidates?.[branch]?.protocol||null;
 return trial?.comparisons?.[branch]?.protocol||results?.[branch]||null;
}
function render(branch){
 const candidate=trial?.candidates?.[branch];
 const r=protocolFor(branch);
 document.querySelectorAll('[data-branch]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.branch===branch)));
 const parent=byId('caseRows');parent.replaceChildren();
 const isCandidate=Object.prototype.hasOwnProperty.call(candidateNames,branch);
 byId('candidateDetails').hidden=!isCandidate;
 byId('score').textContent=r?`${r.passed} / ${r.total}`:'Not evaluated';
 byId('fill').style.width=r?`${r.passed/r.total*100}%`:'0%';
 byId('resultProvenance').textContent=isCandidate?'INDEPENDENT SANDBOX RESULTS':trial?.comparisons?.[branch]?.protocol?'CURRENT SANDBOX COMPARISON':'HISTORICAL RECORDED COMPARISON';
 byId('summary').textContent=isCandidate?
   `${candidateNames[branch]}: ${candidate?.status||'unavailable'}. ${candidate?.provenance||'No candidate evidence is available.'}`:labels[branch];
 if(r){
  r.cases.forEach(c=>{
   const row=document.createElement('div');row.className='case';
   const label=document.createElement('span');label.textContent=c.case.replaceAll('_',' ');
   const status=document.createElement('span');status.className=c.passed?'pass':'fail';status.textContent=c.passed?'PASS':'FAIL';
   row.append(label,status);
   if(c.failures?.length)row.title=c.failures.join('; ');
   parent.appendChild(row);
  });
 }else{const p=document.createElement('p');p.className='empty-evidence';p.textContent='No independent sandbox outcome is recorded. Historical claims are listed separately below.';parent.appendChild(p);}
 const supplemental=isCandidate?candidate?.supplemental:trial?.comparisons?.[branch]?.supplemental||results?.supplemental?.[branch];
 byId('supplementalScore').textContent=supplemental?`Supplemental: ${supplemental.passed} / ${supplemental.checks}. Post-reference checks; excluded from acceptance.`:'Supplemental checks: not evaluated.';
 if(isCandidate){
  byId('patchTitle').textContent=`${candidateNames[branch]} patch`;
  byId('patchText').textContent=candidate?.patch||'No patch recorded.';
  byId('patchHash').textContent=candidate?.patch_sha256||'No patch hash recorded.';
  byId('scopeResult').textContent=candidate?.scope?JSON.stringify(candidate.scope,null,2):'No scope review recorded.';
  const statements=candidate?.model_statements;
  byId('modelStatements').textContent=statements?JSON.stringify(statements,null,2):'No model statements recorded. Statements are proposals, not test results.';
 }
}
function renderTrial(info){
 if(!info||info.schema_version!==1||!['blocked','failed','completed','missing','invalid'].includes(info.status))throw Error('Invalid trial evidence');
 trial=info;
 byId('trialStatus').textContent=`Source model trial: ${info.status}`;
 byId('trialExplain').textContent=info.label||info.error||'Recorded source-repair evidence. No inference or code execution occurs in this page.';
 notes(byId('trialBlockers'),info.blockers||[]);
 notes(byId('auditClaims'),info.audit?.claims||['No supplied historical claims are available.']);
 notes(byId('auditLimits'),info.audit?.limitations||[]);
 notes(byId('validationNotes'),info.validation?.observations||[]);
 const details=byId('transportDetails');details.replaceChildren();
 const t=info.transport;
 if(!t){textRow(details,'Transport','No direct transport evidence recorded.');}
 else{
  const fields={status:'Transport status',requested_model:'Requested model',returned_model:'Returned model',response_id:'Response ID',provider_request_id:'Provider request ID',finish_reason:'Finish reason',reserved_at_utc:'Reserved (UTC)',sent_at_utc:'Sent (UTC)',received_at_utc:'Received (UTC)',request_sha256:'Request SHA-256',response_sha256:'Response SHA-256',patch_sha256:'Proposed patch SHA-256'};
  for(const [key,label] of Object.entries(fields))if(t[key]!==null&&t[key]!==undefined)textRow(details,label,t[key]);
  textRow(details,'Observed usage',t.usage===null||t.usage===undefined?'No provider usage observed.':JSON.stringify(t.usage,null,2));
 }
 const details02=byId('transportDetails02');
 if(details02){
  details02.replaceChildren();
  const t2=info.transport_02;
  if(!t2){textRow(details02,'Second transport','No second direct transport evidence recorded.');}
  else{
   const fields={status:'Transport status',requested_model:'Requested model',returned_model:'Returned model',response_id:'Response ID',provider_request_id:'Provider request ID',finish_reason:'Finish reason',reserved_at_utc:'Reserved (UTC)',sent_at_utc:'Sent (UTC)',received_at_utc:'Received (UTC)',request_sha256:'Request SHA-256',response_sha256:'Response SHA-256',patch_sha256:'Proposed patch SHA-256'};
   for(const [key,label] of Object.entries(fields))if(t2[key]!==null&&t2[key]!==undefined)textRow(details02,label,t2[key]);
   textRow(details02,'Observed usage',t2.usage===null||t2.usage===undefined?'No provider usage observed.':JSON.stringify(t2.usage,null,2));
  }
 }
}
async function loadHistorical(){
 try{
  const res=await fetch('/source-repair/results.json',{cache:'no-store'});if(!res.ok)throw Error('data unavailable');
  const data=await res.json();
  if(!data.upstream||!data.reference||!data.supplemental?.reference)throw Error('invalid historical evidence');
  results=data;
  byId('originalScore').textContent=`${results.upstream.passed} / ${results.upstream.total}`;
  byId('referenceScore').textContent=`${results.reference.passed} / ${results.reference.total}`;
  byId('variedScore').textContent=`${results.supplemental.reference.passed} / ${results.supplemental.reference.checks}`;
 }catch(_){byId('summary').textContent='Historical evidence unavailable. See the local JSON and CLI reports.';}
}
async function loadTrial(){
 try{
  const response=await fetch('/source-repair/model-trial.json',{cache:'no-store'});
  if(!response.ok)throw Error('Trial unavailable');
  renderTrial(await response.json());
 }catch(_){renderTrial({schema_version:1,status:'invalid',error:'Trial evidence unavailable or invalid; no model repair result is claimed.'});}
}
async function init(){
 document.querySelectorAll('[data-branch]').forEach(el=>el.addEventListener('click',()=>render(el.dataset.branch)));
 await Promise.all([loadHistorical(),loadTrial()]);render('upstream');
}
init();
