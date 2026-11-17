// Actual frontend client, reusing exact stored fixtures and any explicitly traced inference cache.
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve,join,sep} from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(new URL('../web/package.json',import.meta.url));const ts=require('typescript');
const prior=JSON.parse(readFileSync(process.argv[2],'utf8'));const directory=resolve(process.argv[3]);
if(!directory.startsWith(resolve('.runtime/v4')+sep))throw new Error('Use a fresh V4-only output namespace.');
mkdirSync(directory,{recursive:false});
const nativeFetch=fetch;globalThis.fetch=(url,options)=>nativeFetch(new URL(url,'http://127.0.0.1:8001'),options);
const code=ts.transpileModule(readFileSync('web/src/lib/api.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
const {api,streamMessage}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const original=prior.turns.at(-1);const events=[];const began=performance.now();
const proof={scope:'Actual frontend HTTP/SSE client; saved source reuse, not browser/device acceptance',conversationId:prior.conversationId,question:original.question,attachmentIds:original.attachmentIds,events};
try {
  proof.health=await api('/health');
  await streamMessage({conversation_id:prior.conversationId,content:original.question,attachment_ids:original.attachmentIds,mode:'investigate',request_id:crypto.randomUUID()},new AbortController().signal,event=>events.push({...event,receivedMs:performance.now()-began}));
  proof.elapsedMs=performance.now()-began;const last=events.at(-1);proof.status=last?.status;
  proof.trace=await api('/runs/'+last.metadata.orchestration.run_id+'/trace');
  proof.reloaded=await api('/conversations/'+prior.conversationId);
  if(last.metadata.investigation_id){
    const report=await api('/evidence-investigations/'+last.metadata.investigation_id+'/report',{});proof.report=report;
    for(const format of ['pdf','markdown']){const response=await fetch('/api/v1/reports/'+report.id+'/download?format='+format);if(!response.ok)throw new Error('Report download '+response.status);const bytes=Buffer.from(await response.arrayBuffer());if(!bytes.length||(format==='pdf'&&!bytes.subarray(0,5).equals(Buffer.from('%PDF-'))))throw new Error('Invalid actual report');writeFileSync(join(directory,'report.'+(format==='pdf'?'pdf':'md')),bytes);}
  }
}catch(error){proof.error={name:error.name,message:error.message};proof.status='error';}
writeFileSync(join(directory,'verification.json'),JSON.stringify(proof,null,2));
console.log(JSON.stringify({status:proof.status,elapsedMs:proof.elapsedMs,error:proof.error,steps:proof.trace?.steps?.map(s=>({tool:s.tool_id,status:s.status,elapsed:s.elapsed_seconds})),report:proof.report},null,2));
