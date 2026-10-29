// Shared by microphone capture, the audible demo, and deterministic tests.
export class TurnDetector {
  constructor(rate, {silenceMs=1100, threshold=.012, maxSeconds=25}={}) {
    this.rate=rate; this.silence=rate*silenceMs/1000; this.threshold=threshold;
    this.limit=rate*maxSeconds; this.reset();
  }
  reset(){this.pre=[];this.preSize=0;this.parts=[];this.size=0;this.voiced=0;this.quiet=0;this.active=false;}
  push(samples){
    const chunk=new Float32Array(samples);
    const rms=Math.sqrt(chunk.reduce((n,v)=>n+v*v,0)/chunk.length);
    const voice=rms>this.threshold;
    if(!this.active){
      this.pre.push(chunk);this.preSize+=chunk.length;
      while(this.preSize>this.rate*.3 && this.pre.length>1)this.preSize-=this.pre.shift().length;
      if(!voice)return null;
      this.active=true;this.parts=this.pre;this.size=this.preSize;this.pre=[];this.preSize=0;
    }else{this.parts.push(chunk);this.size+=chunk.length;}
    if(voice){this.voiced+=chunk.length;this.quiet=0;}else this.quiet+=chunk.length;
    if(this.quiet>=this.silence || this.size>=this.limit){
      const valid=this.voiced>=this.rate*.22;
      const out=new Float32Array(this.size);let offset=0;
      for(const part of this.parts){out.set(part,offset);offset+=part.length;}
      this.reset();return valid?out:null;
    }
    return null;
  }
}
export function wavBytes(samples,rate){
  const count=Math.floor(samples.length*16000/rate), buffer=new ArrayBuffer(44+count*2),v=new DataView(buffer);
  const text=(at,s)=>{for(let i=0;i<s.length;i++)v.setUint8(at+i,s.charCodeAt(i));};
  text(0,'RIFF');v.setUint32(4,36+count*2,true);text(8,'WAVE');text(12,'fmt ');
  v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,16000,true);
  v.setUint32(28,32000,true);v.setUint16(32,2,true);v.setUint16(34,16,true);text(36,'data');v.setUint32(40,count*2,true);
  // Average source samples per output sample; capture requests 16 kHz where supported.
  for(let i=0;i<count;i++){
    const from=Math.floor(i*rate/16000),to=Math.max(from+1,Math.floor((i+1)*rate/16000));
    let sum=0;for(let j=from;j<to;j++)sum+=samples[j]||0;
    const s=Math.max(-1,Math.min(1,sum/(to-from)));v.setInt16(44+i*2,s<0?s*32768:s*32767,true);
  }
  return new Uint8Array(buffer);
}
