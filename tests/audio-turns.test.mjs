import test from 'node:test';
import assert from 'node:assert/strict';
import {TurnDetector,wavBytes} from '../frontend/components/conversation/audio.mjs';
const frame=amplitude=>new Float32Array(160).fill(amplitude);
test('silence and a click never submit a turn',()=>{
  const d=new TurnDetector(16000);let results=[];
  for(let i=0;i<300;i++)results.push(d.push(frame(i===100?.3:0)));
  assert.ok(results.every(r=>r===null));
});
test('two utterances emit once each after the silence threshold',()=>{
  const d=new TurnDetector(16000);const results=[];
  for(let turn=0;turn<2;turn++){
    for(let i=0;i<60;i++)assert.equal(d.push(frame(.1)),null);
    for(let i=0;i<150;i++){const r=d.push(frame(0));if(r)results.push(r);}
  }
  assert.equal(results.length,2);assert.ok(results.every(r=>r.length<16000*3));
});
test('long speech is bounded and reset drops partial audio',()=>{
  const d=new TurnDetector(16000,{maxSeconds:1});let count=0;
  for(let i=0;i<100;i++)if(d.push(frame(.1)))count++;
  assert.equal(count,1);d.push(frame(.1));d.reset();
  for(let i=0;i<120;i++)assert.equal(d.push(frame(0)),null);
});
test('WAV output is mono 16 kHz PCM regardless of device sample rate',()=>{
  const bytes=wavBytes(new Float32Array(48000).fill(.25),48000),v=new DataView(bytes.buffer);
  assert.equal(bytes.length,32044);assert.equal(v.getUint32(24,true),16000);
  assert.equal(v.getUint16(22,true),1);assert.equal(v.getUint16(34,true),16);
  assert.ok(v.getInt16(44,true)>8000);
});
