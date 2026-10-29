import test from 'node:test';
import assert from 'node:assert/strict';
import {summarize,csv,pairedDifferences} from '../frontend/lab/stats.mjs';
import {PlaybackClock,recoverySnapshot} from '../frontend/lab/measurement.mjs';
test('summary excludes failed or absent playback, reports counts and nearest-rank p95',()=>{
 const s=summarize([{mode:'streaming',status:'completed',browser_first_playback_ms:1000},{mode:'streaming',status:'completed',browser_first_playback_ms:3000},{mode:'streaming',status:'failed',browser_first_playback_ms:20},{mode:'streaming',status:'completed',browser_first_playback_ms:null}])[0];
 assert.equal(s.n,2);assert.equal(s.total,4);assert.equal(s.failed,1);assert.equal(s.median,2000);assert.equal(s.p95,null);
});
test('warmups excluded and p95 only appears with twenty measured samples',()=>{
 const runs=Array.from({length:20},(_,i)=>({mode:'streaming',status:'completed',browser_first_playback_ms:(i+1)*100}));runs.push({mode:'streaming',phase:'warmup',status:'completed',browser_first_playback_ms:100000});const s=summarize(runs)[0];assert.equal(s.n,20);assert.equal(s.p95,1900);
});
test('paired effects match input and repetition, interval needs five pairs',()=>{
 const runs=[];for(let trial=1;trial<=5;trial++)for(const mode of ['buffered','streaming'])runs.push({mode,trial,audio_sha256:'same',status:'completed',browser_first_playback_ms:mode==='buffered'?3000:2000});runs.push({mode:'streaming',trial:1,audio_sha256:'different',status:'completed',browser_first_playback_ms:1});const p=pairedDifferences(runs)[0];assert.equal(p.n,5);assert.equal(p.median_delta_ms,-1000);assert.deepEqual(p.bootstrap_95_ci_ms,[-1000,-1000]);
});
test('packet clock records first receipt, lead and delayed packet gaps separately',()=>{
 const c=new PlaybackClock();assert.equal(c.packet(1,2000,1000,1600),1.08);c.packet(1.1,2100,1000,1600);assert.equal(c.gaps,0);c.packet(1.5,2500,1000,1600);assert.equal(c.gaps,1);assert.equal(c.metrics().scheduled_playback_ms,1080);assert.equal(c.metrics().first_pcm_received_ms,1000);assert.ok(c.metrics().scheduled_gap_ms>200);
});
test('recovery keeps partial evidence but strips ephemeral audio URLs',()=>{
 const saved=recoverySnapshot([{status:'interrupted',runs:[{status:'completed',audio_url:'blob:secret',response:'Evidence'}]}]);assert.equal(saved[0].runs[0].audio_url,undefined);assert.equal(saved[0].runs[0].response,'Evidence');
});
test('CSV retains missing data and escapes quotes',()=>{
 const out=csv([{mode:'streaming',trial:1,status:'failed',trace_id:'a"b',metrics:{stt_ms:200}}]);assert.ok(out.includes('"a""b"'));assert.ok(out.includes('"200"'));assert.ok(out.includes('""'));
});
