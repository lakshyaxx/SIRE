import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';import {createRequire} from 'node:module';
const require=createRequire(new URL('../package.json',import.meta.url));const ts=require('typescript');
async function source(path){const js=ts.transpileModule(readFileSync(new URL(path,import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;return import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));}
const {PcmFrames}=await source('../src/features/chat/pcm.ts');const {streamMessage}=await source('../src/lib/api.ts');
test('PCM framing preserves every sample across arbitrary worklet block boundaries',()=>{
 const values=new Float32Array([-1,-.5,0,.5,1,.25,-.25]);const one=new PcmFrames(3);const split=new PcmFrames(3);
 const a=[...one.push(values),one.flush()];const b=[...split.push(values.slice(0,2)),...split.push(values.slice(2,6)),...split.push(values.slice(6)),split.flush()];
 const bytes=chunks=>Buffer.concat(chunks.map(chunk=>Buffer.from(chunk)));assert.deepEqual(bytes(a),bytes(b));assert.equal(bytes(a).length,values.length*2);assert.equal(bytes(a).readInt16LE(0),-32768);assert.equal(bytes(a).readInt16LE(8),32767);
 assert.throws(()=>new PcmFrames().push(new Float32Array([NaN])),/non-finite/);
});
test('actual frontend client handles accepted background work without inventing an SSE completion',async()=>{
 const original=globalThis.fetch;const events=[];globalThis.fetch=async()=>new Response(JSON.stringify({type:'investigation_job',job:{id:'test-only-job',status:'queued'}}),{status:202,headers:{'Content-Type':'application/json'}});
 try{await streamMessage({background_if_deep:true},new AbortController().signal,event=>events.push(event));assert.deepEqual(events.map(event=>event.type),['investigation_job']);assert.equal(events[0].job.status,'queued');}finally{globalThis.fetch=original;}
});
