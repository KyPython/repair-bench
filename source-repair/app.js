'use strict';
const labels={upstream:'The unchanged conversion loses content-filter details and exposes incomplete calls.',cosmetic:'A warning is restored, but the tool call is still available for execution.',stoponly:'The stop reason is improved, but partial calls and missing details remain.',toolsonly:'Partial calls are suppressed, but the stop reason and filter evidence can still be wrong.',reference:'The reference keeps normal calls, hides incomplete ones, and preserves block evidence.'};
let results=null;
function render(branch){
 if(!results || !Object.prototype.hasOwnProperty.call(results,branch))return;
 const r=results[branch];
 document.querySelectorAll('[data-branch]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.branch===branch)));
 document.getElementById('score').textContent=`${r.passed} / ${r.total}`;
 document.getElementById('fill').style.width=`${r.passed/r.total*100}%`;
 document.getElementById('summary').textContent=labels[branch];
 const parent=document.getElementById('caseRows');parent.replaceChildren();
 r.cases.forEach(c=>{const row=document.createElement('div');row.className='case'; const label=document.createElement('span');label.textContent=c.case.replaceAll('_',' '); const status=document.createElement('span'); status.className=c.passed?'pass':'fail';status.textContent=c.passed?'PASS':'FAIL';row.append(label,status);parent.appendChild(row)});
}
(async()=>{try{
 const res=await fetch('/source-repair/results.json',{cache:'no-store'});if(!res.ok)throw new Error('data unavailable');
 results=await res.json();render('upstream');
 document.getElementById('originalScore').textContent=`${results.upstream.passed} / ${results.upstream.total}`;
 document.getElementById('referenceScore').textContent=`${results.reference.passed} / ${results.reference.total}`;
 document.getElementById('variedScore').textContent=`${results.supplemental.reference.passed} / ${results.supplemental.reference.checks}`;
 document.querySelectorAll('[data-branch]').forEach(el=>el.addEventListener('click',()=>render(el.dataset.branch)));
 }catch(e){document.getElementById('summary').textContent='Evidence unavailable. See the local JSON and CLI reports.';}
})();
