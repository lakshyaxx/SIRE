/** Conservative playback isolation. VAD onset alone is not proof of deliberate barge-in. */
export class VoiceGate {
  private playing=new Set<string>();private until=0;
  constructor(private cooldownMs=500){}
  configure(cooldownMs:number):void{this.cooldownMs=cooldownMs;}
  update(id:string,state:string,now:number):void {
    if(['buffering','speaking','paused','ready'].includes(state))this.playing.add(id);
    else if(this.playing.delete(id))this.until=Math.max(this.until,now+this.cooldownMs);
  }
  blocked(now:number):boolean{return this.playing.size>0||now<this.until;}
  interrupt():void{this.playing.clear();this.until=0;}
}
