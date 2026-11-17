/** Deterministic PCM16 framing; chunk boundaries cannot duplicate or omit microphone samples. */
export class PcmFrames {
  private pending:number[]=[];
  constructor(private size=2048){}
  push(samples:Float32Array):ArrayBuffer[]{
    for(const value of samples){if(!Number.isFinite(value))throw new Error('Microphone returned a non-finite sample.');this.pending.push(value);}
    const frames:ArrayBuffer[]=[];while(this.pending.length>=this.size)frames.push(this.take(this.size));return frames;
  }
  private take(count:number):ArrayBuffer{const samples=this.pending.splice(0,count);const buffer=new ArrayBuffer(samples.length*2);const view=new DataView(buffer);samples.forEach((sample,index)=>{const value=Math.max(-1,Math.min(1,sample));view.setInt16(index*2,value<0?value*32768:value*32767,true);});return buffer;}
  flush():ArrayBuffer{return this.take(this.pending.length);}
  reset():void{this.pending=[];}
}
