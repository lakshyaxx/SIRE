/** Local inline speech: display text only, bounded chunks, cancellation and honest playback state. */
export function safeSpeechText(text:string):string {
  return text.replace(/```[\s\S]*?```/g,' ').replace(/~~~[\s\S]*?~~~/g,' ')
    .replace(/\[(?:(?:EV|SRC|HYP):[^\]]+|[a-f\d]{24}|[a-f\d]{32}(?::(?:transcript|schema|visual:\d+))?|(?:user|prediction):[a-f\d]{32}|E\d+)\]/gi,' ')
    .replace(/\[([^\]]+)\]\([^)]+\)/g,'$1').replace(/https?:\/\/\S+|www\.\S+/gi,' ')
    .replace(/\b(?:EV|SRC|HYP):[a-f\d]{16,}\b/gi,' ').replace(/<[^>]+>/g,' ')
    .replace(/^[\s#>*|_-]+/gm,' ').replace(/[`*_]/g,'').replace(/\s+/g,' ').trim();
}

export function speechChunks(text:string,limit=220):string[] {
  const words=safeSpeechText(text).split(/\s+/).filter(Boolean);const chunks:string[]=[];let current='';
  for(const word of words){if(word.length>limit)throw new Error('A long token cannot be spoken safely. Use the displayed text.');if(current.length+word.length+1>limit){chunks.push(current);current='';}current=current?`${current} ${word}`:word;}
  if(current)chunks.push(current);return chunks;
}

export type SpeechUpdate={state:'idle'|'buffering'|'speaking'|'paused'|'ready'|'error';chunk?:number;total?:number;error?:string;firstAudioMs?:number;model?:string};

export class InlineSpeech {
  private abort:AbortController|null=null;private generation=0;private request='';private rejectPlayback:((reason:unknown)=>void)|null=null;private urls=new Set<string>();
  private playbackId=crypto.randomUUID();
  constructor(private audio:HTMLAudioElement,private update:(state:SpeechUpdate)=>void){const callback=this.update;this.update=state=>{callback(state);if(typeof window!=='undefined')window.dispatchEvent(new CustomEvent('sire:playback-state',{detail:{id:this.playbackId,state:state.state}}));};}
  stop():void {
    this.generation++;this.abort?.abort();this.rejectPlayback?.(new DOMException('Speech stopped','AbortError'));this.rejectPlayback=null;
    if(this.request)void fetch('/api/v1/voice/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:this.request})}).catch(()=>{});
    this.request='';this.audio.pause();this.audio.removeAttribute('src');this.audio.load();for(const url of this.urls)URL.revokeObjectURL(url);this.urls.clear();this.update({state:'idle'});
  }
  pause():void{this.audio.pause();this.update({state:'paused'});}
  async resume():Promise<void>{try{await this.audio.play();this.update({state:'speaking'});}catch{this.update({state:'ready',error:'Playback was blocked. Press the audio player Play button.'});}}
  async speak(text:string):Promise<void> {
    this.stop();const generation=this.generation;const chunks=speechChunks(text);if(!chunks.length){this.update({state:'error',error:'No display-safe text is available to read.'});return;}
    const began=performance.now();let firstAudioMs:number|undefined;
    type Prepared={response:Response;bytes:Blob}|{error:Error};
    const prepare=async(index:number):Promise<Prepared>=>{
      const abort=new AbortController();const request=crypto.randomUUID();this.abort=abort;this.request=request;
      try{const response=await fetch('/api/v1/voice/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:chunks[index],request_id:request}),signal:abort.signal});if(!response.ok){const body=await response.json();throw new Error(body.error?.message||'Local speech synthesis failed.');}const bytes=await response.blob();if(this.request===request)this.request='';return {response,bytes};}catch(error){return {error:error as Error};}
    };
    let pending:Promise<Prepared>|null=prepare(0);
    for(let index=0;index<chunks.length;index++){
      if(generation!==this.generation)return;
      this.update({state:'buffering',chunk:index+1,total:chunks.length});
      try {
        const prepared=await pending!;if(generation!==this.generation)return;if('error' in prepared)throw prepared.error;
        const {response,bytes}=prepared;
        pending=index+1<chunks.length?prepare(index+1):null;
        const url=URL.createObjectURL(bytes);this.urls.add(url);this.audio.src=url;
        await new Promise<void>((resolve,reject)=>{
          const cleanup=()=>{this.audio.removeEventListener('ended',ended);this.audio.removeEventListener('error',failed);this.audio.removeEventListener('playing',playing);this.audio.removeEventListener('pause',paused);this.rejectPlayback=null;};
          const ended=()=>{cleanup();resolve();};const failed=()=>{cleanup();reject(new Error('The browser could not decode generated speech.'));};
          const playing=()=>{firstAudioMs??=performance.now()-began;this.update({state:'speaking',chunk:index+1,total:chunks.length,firstAudioMs,model:response.headers.get('X-Speech-Model')||'Local speech'});};
          const paused=()=>{if(!this.audio.ended)this.update({state:'paused',chunk:index+1,total:chunks.length});};
          this.rejectPlayback=reason=>{cleanup();reject(reason);};this.audio.addEventListener('ended',ended);this.audio.addEventListener('error',failed);this.audio.addEventListener('playing',playing);this.audio.addEventListener('pause',paused);
          void this.audio.play().catch(()=>this.update({state:'ready',chunk:index+1,total:chunks.length,error:'Browser playback needs a click. Press Play in the inline player.'}));
        });
        URL.revokeObjectURL(url);this.urls.delete(url);
      } catch(error){if(generation!==this.generation||(error as Error).name==='AbortError')return;this.update({state:'error',error:(error as Error).message});return;}
    }
    if(generation===this.generation)this.update({state:'idle',firstAudioMs});
  }
}
