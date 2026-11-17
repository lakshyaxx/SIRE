import test from 'node:test';import assert from 'node:assert/strict';import {readFileSync} from 'node:fs';import {createRequire} from 'node:module';
const require=createRequire(new URL('../package.json',import.meta.url));const ts=require('typescript');
async function source(path){const js=ts.transpileModule(readFileSync(new URL(path,import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;return import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));}
const {collectPages}=await source('../src/lib/pages.ts');const {citationLinks}=await source('../src/lib/citations.ts');
test('history includes the real tail of a multi-page contract and refuses oversized partial displays',async()=>{
  const rows=Array.from({length:5001},(_,index)=>({testOnlySample:index}));const calls=[];
  const result=await collectPages(async(offset,limit)=>{calls.push(offset);return {records:rows.slice(offset,offset+limit),analysis_limit:6000};});
  assert.equal(result.records.length,5001);assert.equal(result.records.at(-1).testOnlySample,5000);assert.deepEqual(calls,[0,5000]);
  await assert.rejects(()=>collectPages(async(offset,limit)=>({records:rows.slice(offset,offset+limit),analysis_limit:5000})),/no partial/);
});
test('only canonical source identities become inspectable links',()=>{
  const id='EV:'+'a'.repeat(64);const transformed=citationLinks(`Reading [${id}] [source limitations]`);
  assert.ok(transformed.includes('#source=EV%3A'));assert.ok(transformed.includes('[source limitations]'));
  assert.equal(citationLinks(transformed),transformed);
});
