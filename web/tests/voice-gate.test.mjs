import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';
const source=readFileSync(new URL('../src/features/chat/voiceGate.ts',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
const {VoiceGate}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
test('playback and cooldown suppress feedback; deliberate interruption enables capture',()=>{
 const gate=new VoiceGate(500);assert.equal(gate.blocked(0),false);
 gate.update('reply','speaking',1);assert.equal(gate.blocked(200),true);
 gate.update('reply','idle',300);assert.equal(gate.blocked(799),true);assert.equal(gate.blocked(800),false);
 gate.update('reply','speaking',900);gate.interrupt();assert.equal(gate.blocked(901),false);
 gate.update('reply','idle',902);assert.equal(gate.blocked(902),false);
});
test('one idle audio component cannot unguard another active player',()=>{
 const gate=new VoiceGate(500);gate.update('one','speaking',1);gate.update('two','idle',2);assert.equal(gate.blocked(1000),true);
 gate.configure(700);assert.equal(gate.blocked(1001),true);
});
test('live VAD candidate cannot invoke cancellation; input provenance is explicit',()=>{
 const voice=readFileSync(new URL('../src/features/chat/VoiceSession.tsx',import.meta.url),'utf8');
 const candidate=voice.slice(voice.indexOf("if(message.type==='speech_started'"),voice.indexOf("if(message.type==='transcribing'"));
 assert(!candidate.includes('onSpeech()'));assert(!candidate.includes('stop-speech'));
 assert(voice.includes('gate.current.blocked(performance.now())'));assert(voice.includes('Interrupt and speak'));
 const chat=readFileSync(new URL('../src/features/chat/Chat.tsx',import.meta.url),'utf8');assert(chat.includes('input_audio_id:inputAudio'));assert(chat.includes("stop('voice_user_interrupt')"));
});
