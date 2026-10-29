// Shared presentation rules are also exercised outside the browser.
export function guidedCriteria({facts='',alternatives='',forbidden='',fields='',action='',amount='',outcome=''}={}){
 const lines=s=>s.split('\n').map(v=>v.trim()).filter(Boolean), expected_fields={};
 for(const line of lines(fields)){const split=line.indexOf('=');if(split<1)throw Error('Use field = value, one expected field per line.');const key=line.slice(0,split).trim(),value=line.slice(split+1).trim();if(!key||!value)throw Error('Each field needs a name and expected value.');expected_fields[key]=value;}
 return {required_facts:lines(facts),acceptable_facts:lines(alternatives).map(line=>line.split('|').map(v=>v.trim()).filter(Boolean)),forbidden_facts:lines(forbidden),expected_fields,...(action?{expected_action:action.trim()}:{}),...(amount!==''?{expected_amount:Number(amount)}:{}),...(outcome?{expected_tool_status:outcome}:{})};
}
export function comparisonRows(runs){
 const latest=new Map();for(const run of runs)if(run.status==='completed'&&run.phase!=='warmup')latest.set(run.mode,run);
 const rows=[...latest.values()].map(run=>{const first=n=>run.events?.find(e=>e.name===n)?.ms,last=n=>run.events?.filter(e=>e.name===n).at(-1)?.ms;
  return {run,firstAudio:first('first_audio_generated'),segments:[['Transcription','stt_request','transcript_ready','var(--stt)'],['Model window','transcript_ready','llm_response_end','var(--llm)'],['Speech window','tts_request','response_complete','var(--tts)']].map(([label,start,end,color])=>({label,start:first(start),end:last(end),color})).filter(s=>Number.isFinite(s.start)&&Number.isFinite(s.end)&&s.end>=s.start)};});
 return {rows,max:Math.max(1,...rows.flatMap(r=>r.segments.map(s=>s.end)),...rows.map(r=>r.firstAudio||0))};
}
export function taskSummary(runs){
 const groups=new Map();for(const r of runs){if(r.phase==='warmup')continue;const key=r.task+':'+r.mode;if(!groups.has(key))groups.set(key,{task:r.task,mode:r.mode,total:0,completed:0,pass:0,scored:0,times:[]});const g=groups.get(key);g.total++;if(r.status==='completed'){g.completed++;if(['pass','fail'].includes(r.evaluation?.status)){g.scored++;g.pass+=r.evaluation.status==='pass';}if(Number.isFinite(r.metrics?.server_first_audio_ms))g.times.push(r.metrics.server_first_audio_ms);}}
 return [...groups.values()];
}
