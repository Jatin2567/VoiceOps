import test from 'node:test';
import assert from 'node:assert/strict';
import {guidedCriteria,comparisonRows,taskSummary} from '../frontend/lab/evidence.mjs';
test('guided checks retain spaces, zero amounts and equals in values',()=>{
 const c=guidedCriteria({facts:'30 days\nreceipt',fields:'name = Alex Test\ncode = a=b',amount:'0',outcome:'blocked'});assert.deepEqual(c.required_facts,['30 days','receipt']);assert.equal(c.expected_fields.code,'a=b');assert.equal(c.expected_amount,0);assert.throws(()=>guidedCriteria({fields:'bad format'}));
});
test('comparison shares a single clock across differently sized runs and preserves overlap',()=>{
 const events=end=>[{name:'stt_request',ms:0},{name:'transcript_ready',ms:100},{name:'llm_response_end',ms:end},{name:'tts_request',ms:200},{name:'first_audio_generated',ms:300},{name:'response_complete',ms:end+100}];const {rows,max}=comparisonRows([{mode:'buffered',status:'completed',events:events(1000)},{mode:'streaming',status:'completed',events:events(500)}]);assert.equal(max,1100);assert.equal(rows[1].segments[2].start,200);assert.equal(rows[1].segments[1].end,500);
});
test('suite summaries keep tasks separate and count failures and unscored responses',()=>{
 const result=taskSummary([{task:'knowledge',mode:'guarded',status:'completed',evaluation:{status:'pass'},metrics:{server_first_audio_ms:10}},{task:'action',mode:'guarded',status:'failed'},{task:'knowledge',mode:'guarded',status:'completed',evaluation:{status:'unscored'}}]);assert.equal(result.length,2);assert.equal(result[0].total,2);assert.equal(result[0].scored,1);assert.equal(result[1].completed,0);
});
