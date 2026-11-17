import {useEffect,useRef,useState} from 'react';
import {api} from '../../lib/api';
import {PcmFrames} from './pcm';
import {InlineSpeech} from './speech';
import {VoiceGate} from './voiceGate';

export type VoiceTurn={turn_id:string;text:string;attachment_id:string};
type Props={disabled:boolean;getConversation:()=>Promise<string>;onTurn:(turn:VoiceTurn)=>Promise<void>;onSpeech:()=>void;onActive:()=>void;onStop:()=>void};

/** Explicit microphone session: server Silero boundaries and final local Whisper, no fake partials. */
export function VoiceSession({disabled,getConversation,onTurn,onSpeech,onActive,onStop}:Props){
  const gate=useRef(new VoiceGate());
  const [state,setState]=useState('idle');const [error,setError]=useState('');const [muted,setMuted]=useState(false);const [transcript,setTranscript]=useState('');const [speaking,setSpeaking]=useState(false);
  const mounted=useRef(true);const acquiring=useRef(false);const stopRequested=useRef(false);const mute=useRef(false);const socket=useRef<WebSocket|null>(null);const media=useRef<MediaStream|null>(null);const context=useRef<AudioContext|null>(null);const node=useRef<AudioWorkletNode|null>(null);const frames=useRef(new PcmFrames());const seen=useRef(new Set<string>());const audio=useRef<HTMLAudioElement|null>(null);const speech=useRef<InlineSpeech|null>(null);const callbacks=useRef({onTurn,onSpeech,onActive,onStop});callbacks.current={onTurn,onSpeech,onActive,onStop};
  function release(){media.current?.getTracks().forEach(track=>track.stop());media.current=null;node.current?.disconnect();node.current=null;void context.current?.close();context.current=null;frames.current.reset();}
  function audit(event:string){if(socket.current?.readyState===WebSocket.OPEN)socket.current.send(JSON.stringify({op:'client_event',event}));}
  function interrupt(){window.dispatchEvent(new Event('sire:stop-speech'));gate.current.interrupt();frames.current.reset();if(socket.current?.readyState===WebSocket.OPEN)socket.current.send(JSON.stringify({op:'reset'}));audit('explicit_interrupt');callbacks.current.onSpeech();setState('listening after deliberate interruption');}
  function stop(){stopRequested.current=true;if(socket.current?.readyState===WebSocket.OPEN)socket.current.send(JSON.stringify({op:'close'}));socket.current?.close();socket.current=null;release();window.dispatchEvent(new Event('sire:stop-speech'));callbacks.current.onStop();if(mounted.current){setState('idle');setMuted(false);}mute.current=false;}
  useEffect(()=>{mounted.current=true;
    if(audio.current)speech.current=new InlineSpeech(audio.current,update=>{if(mounted.current)setSpeaking(['buffering','speaking','paused','ready'].includes(update.state));});
    const silence=()=>speech.current?.stop();const close=()=>stop();const acknowledge=(event:Event)=>{if(socket.current?.readyState===WebSocket.OPEN)void speech.current?.speak(String((event as CustomEvent).detail));};
    const playback=(event:Event)=>{const detail=(event as CustomEvent).detail;const before=gate.current.blocked(performance.now());gate.current.update(detail.id,detail.state,performance.now());if(!before&&gate.current.blocked(performance.now())){frames.current.reset();if(socket.current?.readyState===WebSocket.OPEN)socket.current.send(JSON.stringify({op:'reset'}));audit('playback_blocked');}};
    window.addEventListener('sire:stop-speech',silence);window.addEventListener('sire:voice-session-stop',close);window.addEventListener('sire:voice-ack',acknowledge);window.addEventListener('sire:playback-state',playback);
    return()=>{mounted.current=false;stopRequested.current=true;socket.current?.close();release();speech.current?.stop();window.removeEventListener('sire:stop-speech',silence);window.removeEventListener('sire:voice-session-stop',close);window.removeEventListener('sire:voice-ack',acknowledge);window.removeEventListener('sire:playback-state',playback);};
  },[]);
  async function start(){if(acquiring.current||socket.current)return;acquiring.current=true;stopRequested.current=false;setError('');setState('requesting microphone');
    try{
      const cid=await getConversation();if(!mounted.current||stopRequested.current)return;
      if(!navigator.mediaDevices?.getUserMedia)throw new Error('Live voice requires microphone permission in a supported secure browser. Manual recording remains available.');
      const schema=await api<{audio:{sample_rate:number};playback_guard_ms:number}>('/voice/session-schema');gate.current.configure(schema.playback_guard_ms);const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true},video:false});if(!mounted.current||stopRequested.current){stream.getTracks().forEach(track=>track.stop());return;}media.current=stream;
      const ctx=new AudioContext({sampleRate:schema.audio.sample_rate});context.current=ctx;await ctx.resume();if(ctx.sampleRate!==schema.audio.sample_rate)throw new Error('This browser cannot supply the required local voice sample rate. Use manual recording.');
      const ws=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/v1/voice/session?conversation_id=${encodeURIComponent(cid)}`);socket.current=ws;seen.current.clear();frames.current.reset();mute.current=false;setMuted(false);
      await new Promise<void>((resolve,reject)=>{ws.onopen=()=>resolve();ws.onerror=()=>reject(new Error('Local voice connection failed. Check the server and microphone permissions.'));ws.onclose=()=>reject(new Error('Local voice connection was rejected or closed.'));});
      ws.onmessage=event=>{if(!mounted.current)return;try{const message=JSON.parse(String(event.data));
        if(message.type==='ready'){setState('listening · final transcripts send automatically');callbacks.current.onActive();}
        if(message.type==='speech_started'&&!gate.current.blocked(performance.now())){audit('speech_candidate');setState('possible speech · waiting for final transcript');}
        if(message.type==='transcribing')setState('transcribing locally · final utterance');
        if(message.type==='transcript'&&!seen.current.has(message.turn_id)){seen.current.add(message.turn_id);if(mute.current||gate.current.blocked(performance.now())){audit('transcript_suppressed');return;}setTranscript(message.text);setState('listening · transcript sent');void callbacks.current.onTurn(message as VoiceTurn).catch(reason=>{setTranscript(message.text);setError(`${reason.message} Transcript remains shown; copy it into the composer to retry.`);});}
        if(message.type==='error')setError(message.message);
        if(message.type==='closed'){release();setState('idle');socket.current=null;}
      }catch(reason){setError((reason as Error).message);}};
      ws.onclose=()=>{release();socket.current=null;if(mounted.current){setState('idle');if(!stopRequested.current)setError('Voice session ended. Start it again to continue.');}};ws.onerror=()=>{if(mounted.current)setError('Local voice connection failed; no transcript was substituted.');};
      const url=URL.createObjectURL(new Blob(["class Capture extends AudioWorkletProcessor{process(inputs){const samples=inputs[0]?.[0];if(samples)this.port.postMessage(samples.slice());return true;}}registerProcessor('sire-session-capture',Capture);"],{type:'text/javascript'}));try{await ctx.audioWorklet.addModule(url);}finally{URL.revokeObjectURL(url);}
      if(!mounted.current||stopRequested.current){stop();return;}
      const source=ctx.createMediaStreamSource(stream);const processor=new AudioWorkletNode(ctx,'sire-session-capture');node.current=processor;processor.port.onmessage=event=>{if(mute.current||gate.current.blocked(performance.now())||ws.readyState!==WebSocket.OPEN)return;try{for(const frame of frames.current.push(event.data as Float32Array)){if(ws.bufferedAmount>65536)throw new Error('Voice transport is behind; stop and retry instead of dropping samples silently.');ws.send(frame);}}catch(reason){setError((reason as Error).message);stop();}};const silent=ctx.createGain();silent.gain.value=0;source.connect(processor);processor.connect(silent);silent.connect(ctx.destination);
    }catch(reason){release();socket.current?.close();socket.current=null;if(mounted.current){setError((reason as Error).message);setState('idle');}}finally{acquiring.current=false;}
  }
  const active=state!=='idle';
  return <div className="voice-controls">{!active?<button type="button" disabled={disabled} onClick={start}>Start live voice · send final transcripts</button>:<><span role="status">{state}</span><button type="button" onClick={()=>{mute.current=!mute.current;setMuted(mute.current);media.current?.getAudioTracks().forEach(track=>track.enabled=!mute.current);frames.current.reset();if(socket.current?.readyState===WebSocket.OPEN)socket.current.send(JSON.stringify({op:'reset'}));}}>{muted?'Unmute microphone':'Mute microphone'}</button><button type="button" onClick={interrupt}>Interrupt and speak</button><button type="button" onClick={()=>{const ws=socket.current;if(ws?.readyState===WebSocket.OPEN){const tail=frames.current.flush();if(tail.byteLength)ws.send(tail);ws.send(JSON.stringify({op:'flush'}));}}}>Send utterance now</button><button type="button" onClick={stop}>Stop voice session</button></>}{transcript&&<p>Automatic transcript — unverified: {transcript}</p>}{error&&<p role="alert" className="error">{error}</p>}<audio ref={audio} controls hidden={!speaking} aria-label="Voice-session acknowledgement playback"/><small>Local Silero turn detection and English Whisper. This session sends final transcripts automatically. Manual recording below allows review first. Microphone starts only with permission; microphone capture pauses during playback. Use Interrupt and speak for deliberate interruption; speech detection alone does not stop an answer.</small></div>;
}
