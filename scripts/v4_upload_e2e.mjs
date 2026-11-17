// Actual frontend API module -> owned loopback server -> installed local providers.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { resolve, join, sep } from 'node:path';
const require = createRequire(new URL('../web/package.json', import.meta.url));
const ts = require('typescript');
const origin = process.argv[2] || 'http://127.0.0.1:8001';
const corpus = process.argv[3];
if (!corpus || !/^http:\/\/127\.0\.0\.1:8001$/.test(origin)) throw new Error('Use the owned disposable QA8001 server and public corpus path.');
const output = resolve(process.argv[4] || '.runtime/v4/upload_e2e');
if(!output.startsWith(resolve('.runtime/v4')+sep)) throw new Error('Keep result output inside the disposable V4 namespace.');
mkdirSync(output, {recursive:false});
const requests = [];
const nativeFetch = globalThis.fetch;
globalThis.fetch = async (url, options) => {
  const started=performance.now();
  const response=await nativeFetch(new URL(url,origin),options);
  requests.push({path:String(url),method:options?.method||'GET',status:response.status,headersSent:options?.headers||null,elapsedMs:performance.now()-started});
  return response;
};
const source=readFileSync(new URL('../web/src/lib/api.ts',import.meta.url),'utf8');
const javascript=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
const {api,streamMessage}=await import('data:text/javascript;base64,'+Buffer.from(javascript).toString('base64'));
const proof={scope:'Actual frontend API client invoked under Node with real multipart/network/SSE. Not a browser picker or physical microphone/speaker pass.',apiClientSha256:createHash('sha256').update(source).digest('hex'),origin,uploads:[],turns:[],requests};
async function turn(cid,question,ids=[],mode='chat') {
  const events=[]; const began=performance.now();
  await streamMessage({conversation_id:cid,request_id:crypto.randomUUID(),content:question,attachment_ids:ids,mode},new AbortController().signal,event=>events.push({...event,receivedMs:performance.now()-began}));
  const last=events.at(-1);const result={question,attachmentIds:ids,events,elapsedMs:performance.now()-began,status:last?.status,
    answer:events.filter(e=>e.type==='delta'||e.type==='report').map(e=>e.text||e.content||'').join('')};
  const rid=last?.metadata?.orchestration?.run_id;
  if(rid)result.trace=await api(`/runs/${rid}/trace`);
  proof.turns.push(result);writeFileSync(join(output,'verification.json'),JSON.stringify(proof,null,2));
  return result;
}
try {
  const c=await api('/conversations',{title:'V4 real frontend-client upload acceptance'});proof.conversationId=c.id;
  if(process.argv[5]!=='repair')await turn(c.id,'Hi SIRE');
  for(const relative of ['media/images/bearing_corrosion_schematic.png','documents/facility_maintenance_handbook.pdf','test_inputs/valid/telemetry_small.csv','documents/maintenance_work_order.docx','documents/sire_maintenance_workbook.xlsx']) {
    const bytes=readFileSync(join(corpus,relative));const form=new FormData();form.append('conversation_id',c.id);form.append('file',new File([bytes],relative.split('/').at(-1)));
    const began=performance.now();const receipt=await api('/attachments',form);
    proof.uploads.push({fixture:relative,originalSha256:createHash('sha256').update(bytes).digest('hex'),receipt,elapsedMs:performance.now()-began});
  }
  const [image,pdf,csv]=proof.uploads.map(u=>u.receipt.id);
  if(process.argv[5]!=='repair') {
    await turn(c.id,'What does this synthetic schematic depict? Distinguish visible labels from physical damage or invisible internal measurements.',[image]);
    await turn(c.id,'According to the uploaded maintenance handbook, what evidence and inspection records should be collected? Cite its actual page text.',[pdf]);
  }
  await turn(c.id,'Summarize the exact descriptive sensor statistics and units from this uploaded CSV. These are synthetic measurements, not NASA turbofan inputs.',[csv]);
  await turn(c.id,'Compare possible explanations for the depicted issue using the uploaded schematic, manual and measurements. Cite actual evidence, state missing association and never treat the image as proof of hidden damage.',[image,pdf,csv],'investigate');
  proof.reloaded=await api('/conversations/'+c.id);
  proof.status=proof.turns.every(t=>t.status==='complete')?'COMPLETED_REQUESTS_NEED_SEMANTIC_REVIEW':'INCOMPLETE';
} catch(error) {proof.status='ERROR';proof.error={name:error.name,message:error.message};}
writeFileSync(join(output,'verification.json'),JSON.stringify(proof,null,2));
console.log(JSON.stringify({status:proof.status,uploads:proof.uploads.length,turns:proof.turns.map(t=>({status:t.status,elapsedMs:t.elapsedMs,tools:t.trace?.steps?.map(s=>s.tool_id)})),error:proof.error},null,2));
if(proof.status==='ERROR')process.exitCode=1;
