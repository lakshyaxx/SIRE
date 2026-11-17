import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(new URL('../package.json',import.meta.url));const ts=require('typescript');
const javascript=ts.transpileModule(readFileSync(new URL('../src/features/chat/speech.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
const {safeSpeechText,speechChunks,InlineSpeech}=await import('data:text/javascript;base64,'+Buffer.from(javascript).toString('base64'));

test('speech excludes opaque sources/code/URLs and preserves displayed quantities',()=>{
  const text='## Reading 2.685 mm/s [EV:'+'a'.repeat(64)+'] [manual](https://example.test/path) ```secret trace```';
  assert.equal(safeSpeechText(text),'Reading 2.685 mm/s manual');
  const chunks=speechChunks('Exact test-only words. '.repeat(30));
  assert.ok(chunks.every(chunk=>chunk.length<=220));assert.equal(chunks.join(' '),safeSpeechText('Exact test-only words. '.repeat(30)));
});

class TestOnlyAudio extends EventTarget {
  src='';ended=false;playCalls=0;paused=true;
  async play(){this.playCalls++;this.paused=false;this.dispatchEvent(new Event('playing'));}
  pause(){this.paused=true;this.dispatchEvent(new Event('pause'));}
  removeAttribute(){this.src='';}
  load(){}
}

test('actual inline controller requests speech then calls play without a download/navigation',async context=>{
  const original=globalThis.fetch;context.after(()=>globalThis.fetch=original);const calls=[];
  globalThis.fetch=async(url,options)=>{calls.push({url,body:JSON.parse(options.body)});return new Response(new Blob(['explicit test-only media bytes']),{headers:{'Content-Type':'audio/wav','X-Speech-Model':'test-only-contract-provider'}});};
  const audio=new TestOnlyAudio();const states=[];const session=new InlineSpeech(audio,state=>states.push(state));const finished=session.speak('Explicit test-only speech contract.');
  for(let tries=0;tries<100&&!audio.playCalls;tries++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(audio.playCalls,1);assert.equal(calls[0].url,'/api/v1/voice/speak');assert.ok(states.some(state=>state.state==='speaking'));
  session.pause();assert.equal(states.at(-1).state,'paused');await session.resume();assert.equal(audio.playCalls,2);
  audio.ended=true;audio.dispatchEvent(new Event('ended'));await finished;assert.equal(states.at(-1).state,'idle');
});

test('stop aborts an in-flight request and sends its exact cancellation ID',async context=>{
  const original=globalThis.fetch;context.after(()=>globalThis.fetch=original);const calls=[];let aborted=false;
  globalThis.fetch=(url,options)=>{calls.push({url,body:JSON.parse(options.body)});if(url.endsWith('/cancel'))return Promise.resolve(new Response('{}'));
    return new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>{aborted=true;reject(new DOMException('Test-only aborted request','AbortError'));}));};
  const audio=new TestOnlyAudio();const states=[];const session=new InlineSpeech(audio,state=>states.push(state));const finished=session.speak('Explicit cancellation contract.');session.stop();await finished;
  assert.equal(aborted,true);assert.equal(audio.playCalls,0);assert.equal(calls[0].body.request_id,calls[1].body.request_id);assert.equal(states.at(-1).state,'idle');
});

test('one speech chunk is prepared ahead while the current chunk plays and stop prevents further chunks',async context=>{
 const original=globalThis.fetch;context.after(()=>globalThis.fetch=original);const calls=[];
 globalThis.fetch=async(url,options)=>{calls.push(url);return new Response(new Blob(['explicit test-only audio transport']),{headers:{'Content-Type':'audio/wav'}});};
 const audio=new TestOnlyAudio();const session=new InlineSpeech(audio,()=>{});const finished=session.speak('Explicit test-only segment. '.repeat(30));
 for(let tries=0;tries<100&&(!audio.playCalls||calls.length<2);tries++)await new Promise(resolve=>setImmediate(resolve));
 assert.equal(audio.playCalls,1);assert.equal(calls.filter(url=>url.endsWith('/speak')).length,2);assert.equal(audio.ended,false);
 session.stop();await finished;assert.equal(audio.playCalls,1);
});
