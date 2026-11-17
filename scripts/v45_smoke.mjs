// Actual shipped API client against a disposable loopback V4.5 server; no browser/device claim.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {createRequire} from 'node:module';
import {createHash,randomUUID} from 'node:crypto';
import {resolve,join,sep} from 'node:path';

const require=createRequire(new URL('../web/package.json',import.meta.url));
const ts=require('typescript');
const origin='http://127.0.0.1:8001';
const corpus=resolve(process.argv[2]||'');
const output=resolve(process.argv[3]||'.runtime/v45/client_smoke');
const imageRelative=process.argv[4]||'media/images/bearing_corrosion_schematic.png';
if(!['media/images/bearing_corrosion_schematic.png','media/images/bearing_inspection_generated_01.jpg'].includes(imageRelative))throw new Error('Use a named public visual fixture');
if(!corpus.endsWith('SIRE_STRESS_LAB_PUBLIC')||!output.startsWith(resolve('.runtime/v45')+sep))throw new Error('Use only the public corpus and a fresh disposable V45 output directory.');
mkdirSync(output,{recursive:false});
const requests=[];
const networkFetch=globalThis.fetch;
globalThis.fetch=async(url,options)=>{
  const began=performance.now();const response=await networkFetch(new URL(url,origin),options);
  requests.push({path:String(url),method:options?.method||'GET',status:response.status,elapsedMs:performance.now()-began});
  return response;
};
const source=readFileSync(new URL('../web/src/lib/api.ts',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
const {api,streamMessage}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const proof={scope:'Real frontend API module, multipart, SSE/202, saved jobs, source resolution and local models. Browser picker and physical microphone/speaker unverified.',apiClientSha256:createHash('sha256').update(source).digest('hex'),origin,requests,uploads:[],turns:[],checks:[]};
const save=()=>writeFileSync(join(output,'verification.json'),JSON.stringify(proof,null,2));
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function turn(cid,content,attachment_ids=[],extra={}){
  const events=[];const began=performance.now();
  await streamMessage({conversation_id:cid,request_id:randomUUID(),content,attachment_ids,mode:'chat',background_if_deep:true,...extra},new AbortController().signal,event=>events.push({...event,receivedMs:performance.now()-began}));
  const last=events.at(-1);const value={content,attachment_ids,events,elapsedMs:performance.now()-began,status:last?.status||last?.type,answer:events.filter(e=>['delta','report'].includes(e.type)).map(e=>e.text||e.content||'').join('')};
  const run=last?.metadata?.orchestration?.run_id;
  if(run)value.trace=await api('/runs/'+run+'/trace');
  proof.turns.push(value);save();return value;
}
async function check(name,operation){
  const began=performance.now();let row;
  try{row={name,status:'pass',evidence:await operation()};}catch(error){row={name,status:'fail',error:{name:error.name,message:error.message}};}
  row.elapsedMs=performance.now()-began;proof.checks.push(row);save();console.log(JSON.stringify({name,status:row.status,elapsedMs:row.elapsedMs}));return row;
}
try{
  proof.health=await api('/health');
  if(proof.health.application_version!=='4.5.0')throw new Error('QA server is not V4.5');
  proof.residencyBefore=await api('/runtime/resources');
  const conversation=await api('/conversations',{title:'V45 disposable real frontend-client acceptance'});const cid=proof.conversationId=conversation.id;
  await check('ordinary_real_text',async()=>{
    const value=await turn(cid,'Briefly explain what a rolling bearing does in two sentences.');
    if(value.status!=='complete'||!value.answer.trim())throw new Error('No completed actual answer');
    if(value.trace.steps.some(s=>s.tool_id==='hypotheses.investigate'))throw new Error('Ordinary question triggered deep investigation');
    return {turnIndex:proof.turns.length-1,firstStatusMs:value.events.find(e=>e.type==='status')?.receivedMs,firstDeltaMs:value.events.find(e=>e.type==='delta')?.receivedMs,totalMs:value.elapsedMs,tools:value.trace.steps.map(s=>s.tool_id)};
  });
  for(const relative of [imageRelative,'documents/facility_maintenance_handbook.pdf','test_inputs/valid/telemetry_small.csv','documents/maintenance_work_order.docx','documents/sire_maintenance_workbook.xlsx']){
    const bytes=readFileSync(join(corpus,relative));const form=new FormData();form.append('conversation_id',cid);form.append('file',new File([bytes],relative.split('/').at(-1)));
    const began=performance.now();const receipt=await api('/attachments',form);
    const originalSha256=createHash('sha256').update(bytes).digest('hex');
    if((receipt.metadata.original_sha256||receipt.sha256)!==originalSha256)throw new Error('Attachment original source hash differs');
    proof.uploads.push({fixture:relative,originalSha256,storedSha256:receipt.sha256,receipt,elapsedMs:performance.now()-began});save();
  }
  for(const item of proof.uploads.filter(u=>u.receipt.kind==='document')){
    await check('source_supported_document_'+item.receipt.name,async()=>{
      const value=await turn(cid,'According to this document, quote the actual record passages with source locators.',[item.receipt.id]);
      const metadata=value.events.at(-1)?.metadata;
      if(value.status!=='complete'||metadata.response_route!=='exact_retrieved_document_passages'||metadata.model_activity.length)throw new Error('Exact source response missing');
      const supports=[];
      for(const e of metadata.evidence){
        const resolved=await api('/evidence/'+e.id);const obs=resolved.evidence.observation;
        supports.push({id:e.id,support:String(obs.text??obs.excerpt??'').includes(e.observation)});
      }
      if(!supports.length||supports.some(s=>!s.support))throw new Error('Citation excerpt is not supported by actual source');
      return {turnIndex:proof.turns.length-1,supports,verification:metadata.claim_verification};
    });
  }
  const [image,pdf,csv]=proof.uploads.map(u=>u.receipt.id);
  await check('exact_csv_without_NASA',async()=>{
    const value=await turn(cid,'Summarize the exact descriptive sensor statistics and units from this uploaded CSV. These are synthetic measurements, not NASA turbofan inputs.',[csv]);
    if(value.status!=='complete'||value.trace.steps.some(s=>s.tool_id==='prediction.run'))throw new Error('CSV source path failed or incorrectly used NASA');
    return {turnIndex:proof.turns.length-1,tools:value.trace.steps.map(s=>s.tool_id),metadata:value.events.at(-1).metadata};
  });
  const began=performance.now();
  const visualKind=imageRelative.endsWith('.jpg')?'visually generated test photograph':'synthetic schematic';
  const accepted=await turn(cid,`Compare possible explanations for the depicted issue using the uploaded ${visualKind}, manual and measurements. Cite actual evidence, state missing asset association, and never treat this generated image as proof of hidden damage.`,[image,pdf,csv],{mode:'investigate'});
  const jobId=accepted.events.at(-1)?.job?.id;
  if(!jobId)throw new Error('Real background investigation was not accepted');
  proof.background={id:jobId,acceptedMs:accepted.elapsedMs,polls:[]};save();
  const statusCheck=check('same_conversation_status_while_deep',async()=>{
    const value=await turn(cid,'What are you doing right now?');
    if(value.status!=='complete'||!value.trace.steps.some(s=>s.tool_id==='investigation.status')||value.trace.steps.some(s=>s.tool_id==='llm.chat'))throw new Error('Status did not use actual persisted-state tool');
    return {turnIndex:proof.turns.length-1,elapsedMs:value.elapsedMs,tools:value.trace.steps.map(s=>s.tool_id)};
  });
  let job;
  do{
    job=await api('/investigation-jobs/'+jobId+'?conversation_id='+cid);
    const receivedMs=performance.now()-began;
    proof.background.polls.push({status:job.status,receivedMs,events_total:job.events_total});
    if(!proof.background.firstVerifiedFactsMs&&job.events.some(e=>e.type==='delta'&&e.source==='validated_descriptive_measurement_statistics'))proof.background.firstVerifiedFactsMs=receivedMs;
    proof.background.final=job;save();
    if(['complete','partial','error','cancelled','interrupted'].includes(job.status))break;
    if(receivedMs>310000){await api('/investigation-jobs/'+jobId+'/cancel?conversation_id='+cid,{});throw new Error('Smoke investigation exceeded bounded 310s');}
    await pause(1000);
  }while(true);
  await statusCheck;
  proof.background.elapsedMs=performance.now()-began;
  if(job.run_id)proof.background.trace=await api('/runs/'+job.run_id+'/trace');
  proof.reloaded=await api('/conversations/'+cid);
  const message=proof.reloaded.messages.find(m=>m.id===job.assistant_message_id);
  const investigation=message?.metadata?.investigation_id;
  if(investigation){
    proof.background.investigationId=investigation;
    const report=await api('/evidence-investigations/'+investigation+'/report',{});proof.report=report;
    for(const format of ['pdf','markdown','json']){
      const response=await fetch('/api/v1/reports/'+report.id+'/download?format='+format);if(!response.ok)throw new Error('Report download '+response.status);
      writeFileSync(join(output,'report.'+({pdf:'pdf',markdown:'md',json:'json'})[format]),Buffer.from(await response.arrayBuffer()));
    }
  }
  await check('saved_hypothesis_recall_without_reproposal',async()=>{
    const value=await turn(cid,'Which hypotheses did you already consider, and why were any ruled out?');
    if(value.status!=='complete'||value.trace.steps.some(s=>s.tool_id==='hypotheses.investigate'))throw new Error('Recall repeated deep work');
    return {turnIndex:proof.turns.length-1,tools:value.trace.steps.map(s=>s.tool_id),elapsedMs:value.elapsedMs};
  });
  proof.registry=await api('/providers/registry');proof.resourcesAfter=await api('/runtime/resources');
  proof.status=proof.checks.every(c=>c.status==='pass')&&job.status==='complete'?'REQUESTS_COMPLETE_SEMANTIC_REVIEW_REQUIRED':'GAPS_RECORDED';
}catch(error){proof.status='ERROR';proof.error={name:error.name,message:error.message};process.exitCode=1;}
save();console.log(JSON.stringify({status:proof.status,checks:proof.checks.map(c=>({name:c.name,status:c.status})),background:proof.background&&{status:proof.background.final?.status,acceptedMs:proof.background.acceptedMs,firstVerifiedFactsMs:proof.background.firstVerifiedFactsMs,elapsedMs:proof.background.elapsedMs},error:proof.error},null,2));
