import test from 'node:test';
import assert from 'node:assert/strict';
import {summarize,csv} from '../frontend/lab/stats.mjs';
test('summary excludes failed or absent playback, reports counts and nearest-rank p95',()=>{
 const s=summarize([{mode:'streaming',status:'completed',browser_first_playback_ms:1000},{mode:'streaming',status:'completed',browser_first_playback_ms:3000},{mode:'streaming',status:'failed',browser_first_playback_ms:20},{mode:'streaming',status:'completed',browser_first_playback_ms:null}])[0];
 assert.equal(s.n,2);assert.equal(s.total,4);assert.equal(s.failed,1);assert.equal(s.median,2000);assert.equal(s.p95,3000);
});
test('CSV retains missing data and escapes quotes',()=>{
 const out=csv([{mode:'streaming',trial:1,status:'failed',trace_id:'a"b',metrics:{stt_ms:200}}]);assert.ok(out.includes('"a""b"'));assert.ok(out.includes('"200"'));assert.ok(out.includes('""'));
});
