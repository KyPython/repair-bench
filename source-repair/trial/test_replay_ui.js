'use strict';
// DOM replay contract tests. These do not claim HTTP/Chromium/CSP validation.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const historical=JSON.parse(fs.readFileSync(path.join(root,'results.json'),'utf8'));
class Node {
 constructor(){this.textContent='';this.children=[];this.style={};this.dataset={};this.attributes={};this.hidden=false;}
 set innerHTML(_){throw Error('Evidence must never be rendered as HTML');}
 setAttribute(k,v){this.attributes[k]=v;}
 append(...nodes){this.children.push(...nodes);}
 appendChild(node){this.children.push(node);}
 replaceChildren(...nodes){this.children=nodes;}
 addEventListener(k,fn){this[k]=fn;}
}
async function page(evidence){
 const nodes={};const branches=['upstream','cosmetic','stoponly','toolsonly','reference','operator_supplied','direct_meta'].map(branch=>{const n=new Node();n.dataset.branch=branch;return n;});
 const context=vm.createContext({document:{getElementById:id=>nodes[id]??(nodes[id]=new Node()),createElement:()=>new Node(),querySelectorAll:()=>branches},
 fetch:async url=>({ok:true,json:async()=>url.endsWith('results.json')?historical:evidence})});
 const source=fs.readFileSync(path.join(root,'app.js'),'utf8').replace(/init\(\);\s*$/,'globalThis.ready=init();');
 vm.runInContext(source,context);await context.ready;
 return {nodes,context,select:branch=>vm.runInContext(`render(${JSON.stringify(branch)})`,context)};
}
function trial(status='completed'){
 return {schema_version:1,status,transport:{status:'completed',requested_model:'muse-spark-1.3',returned_model:'muse-spark-1.3',response_id:'test-id',usage:{completion_tokens:10,completion_tokens_details:{reasoning_tokens:5}}},
 candidates:{direct_meta:{status:'accepted',provenance:'Separate sandbox run',protocol:historical.reference,supplemental:{passed:18,checks:18},patch:'<script>globalThis.compromised=true</script>',patch_sha256:'a'.repeat(64),scope:{approved:true},model_statements:{diagnosis:'Statement, not a test'}}},
 audit:{claims:['Authorship is unverified'],limitations:['Excerpts only']},validation:{observations:['Sandbox isolation probe passed']}};
}
test('successful candidate renders outcomes and patch as inert text',async()=>{
 const p=await page(trial());p.select('direct_meta');
 assert.equal(p.nodes.score.textContent,'9 / 9');
 assert.equal(p.nodes.caseRows.children.length,9);
 assert.match(p.nodes.patchText.textContent,/<script>/);
 assert.equal(p.context.compromised,undefined);
 assert.match(p.nodes.modelStatements.textContent,/Statement, not a test/);
 assert.match(p.nodes.supplementalScore.textContent,/excluded from acceptance/);
});
test('blocked candidate does not inherit successful reference outcome',async()=>{
 const evidence=trial('blocked');evidence.transport={status:'blocked',usage:null};evidence.candidates.direct_meta={status:'blocked',provenance:'Credit controls unavailable'};
 const p=await page(evidence);p.select('reference');assert.equal(p.nodes.score.textContent,'9 / 9');
 p.select('direct_meta');assert.equal(p.nodes.score.textContent,'Not evaluated');
 assert.equal(p.nodes.fill.style.width,'0%');assert.equal(p.nodes.patchText.textContent,'No patch recorded.');
 assert.match(p.nodes.summary.textContent,/Credit controls unavailable/);
});
test('failed candidate replays actual failure outcomes without calling it accepted',async()=>{
 const evidence=trial('failed');evidence.candidates.direct_meta.status='rejected';evidence.candidates.direct_meta.protocol=historical.upstream;
 const p=await page(evidence);p.select('direct_meta');assert.equal(p.nodes.score.textContent,'4 / 9');
 assert.match(p.nodes.summary.textContent,/rejected/);assert.equal(p.nodes.caseRows.children[0].children[1].textContent,'FAIL');
});
test('missing and invalid trials preserve historical replay and show no model scores',async()=>{
 for(const evidence of [{schema_version:1,status:'missing'}, {schema_version:1,status:'invalid'}, {schema_version:99,status:'completed'}]){
  const p=await page(evidence);assert.equal(p.nodes.score.textContent,'4 / 9');
  p.select('direct_meta');assert.equal(p.nodes.score.textContent,'Not evaluated');
  assert.match(p.nodes.trialStatus.textContent,/missing|invalid/);
 }
});
test('transport observations, supplied claims and independent results stay distinct',async()=>{
 const p=await page(trial());
 assert.equal(p.nodes.auditClaims.children[0].textContent,'Authorship is unverified');
 assert.equal(p.nodes.validationNotes.children[0].textContent,'Sandbox isolation probe passed');
 const texts=p.nodes.transportDetails.children.map(row=>row.children[1].textContent).join(' ');
 assert.match(texts,/test-id/);assert.match(texts,/reasoning_tokens/);
 p.select('operator_supplied');assert.equal(p.nodes.score.textContent,'Not evaluated');
});
