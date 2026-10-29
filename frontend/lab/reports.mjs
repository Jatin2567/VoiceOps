import {median,names} from './stats.mjs';
const KEY='voiceops-reports-v3';
export function cleanReport(value){
 if(!value||typeof value!=='object'||!Array.isArray(value.runs)||value.runs.length>1000||!value.created_at||(!value.spec&&!value.suite_id))throw Error('Choose a VoiceOps comparison or suite report.');
 const report=JSON.parse(JSON.stringify(value, (k,v)=>['audio_url','__proto__','constructor','prototype'].includes(k)?undefined:v));
 report.id=typeof report.id==='string'?report.id:crypto.randomUUID();report.kind=report.suite_id?'suite':'comparison';
 report.status=report.status==='running'?'interrupted':report.status||'completed';
 for(const r of report.runs){if(!r||!names[r.mode]||typeof r.status!=='string')throw Error('The report contains an invalid trial.');r.events=Array.isArray(r.events)?r.events.filter(e=>e&&typeof e.name==='string'&&Number.isFinite(e.ms)):[];r.metrics=r.metrics&&typeof r.metrics==='object'?r.metrics:{};r.tools=Array.isArray(r.tools)?r.tools.filter(t=>t&&typeof t==='object'):[];}
 return report;
}
export class ReportStore extends EventTarget {
 constructor(storage){super();this.storage=storage;this.entries=[];this.persist=false;this.message='Reports stay in this tab until you choose to save.';try{const raw=storage?.getItem(KEY)||storage?.getItem('voiceops-reports-v2');if(raw){const saved=JSON.parse(raw);if(!Array.isArray(saved)||saved.length>100)throw Error();this.entries.push(...saved.map(cleanReport));this.persist=true;this.message='Recovered saved reports. Audio is not retained.';}}catch{this.message='Saved reports could not be read. Import an exported copy to recover.';}}
 checkpoint(report){if(report){const index=this.entries.findIndex(r=>r.id===report.id);if(index<0)this.entries.push(report);else this.entries[index]=report;}if(this.persist){try{this.storage?.setItem(KEY,JSON.stringify(this.entries.map(cleanReport)));this.storage?.removeItem('voiceops-reports-v2');this.message='Comparison and suite reports saved on this browser. Audio is excluded.';}catch{this.message='Browser storage is full or unavailable. Export reports to keep them.';}}this.dispatchEvent(new Event('change'));}
 setPersist(value){this.persist=value;if(!value){try{this.storage?.removeItem(KEY);this.storage?.removeItem('voiceops-reports-v2');}catch{}this.message='Saving disabled. Saved copies removed; tab reports remain.';}this.checkpoint();}
 clear(){this.entries.splice(0);try{this.storage?.removeItem(KEY);this.storage?.removeItem('voiceops-reports-v2');}catch{}this.message='Session and saved reports cleared.';this.dispatchEvent(new Event('change'));}
 import(text){if(text.length>5*1024*1024)throw Error('Choose a report smaller than 5 MB.');const report=cleanReport(JSON.parse(text));this.checkpoint(report);return report;}
}
let storage;try{storage=globalThis.localStorage;}catch{}
export const reports=new ReportStore(storage);
const stable=v=>JSON.stringify(v,(_,value)=>value&&typeof value==='object'&&!Array.isArray(value)?Object.fromEntries(Object.entries(value).sort(([a],[b])=>a.localeCompare(b))):value);
function signature(report,run){
 const spec=report.spec||report.manifest?.cases?.find(c=>c.id===run.case_id)?.spec;
 if(!spec||!run.audio_sha256||!run.providers)return null;
 const {modes,repeats,warmup,order_offset,...settings}=spec;
 return stable({case:run.case_id||'',input:run.audio_sha256,mode:run.mode,settings,providers:run.providers,configuration:run.configuration||{}});
}
export function compareReports(a,b){
 if(a.id===b.id)return {rows:[],message:'Choose two different reports.'};
 const groups=report=>{const map=new Map();for(const r of report.runs){if(r.phase==='warmup')continue;const key=signature(report,r);if(!key)continue;if(!map.has(key))map.set(key,[]);map.get(key).push(r);}return map;};
 const left=groups(a),right=groups(b),rows=[];
 const stats=runs=>{const completed=runs.filter(r=>r.status==='completed'),times=completed.map(r=>r.metrics?.server_first_audio_ms).filter(Number.isFinite),scored=completed.filter(r=>['pass','fail'].includes(r.evaluation?.status));return {total:runs.length,completed:completed.length,failed:runs.length-completed.length,pass:scored.filter(r=>r.evaluation.status==='pass').length,scored:scored.length,median:times.length?median(times):null,n:times.length};};
 for(const [key,runs] of left){if(!right.has(key))continue;const before=stats(runs),after=stats(right.get(key));rows.push({case:runs[0].case_id||a.spec?.task,mode:runs[0].mode,before,after,delta:before.median!==null&&after.median!==null?after.median-before.median:null});}
 const matched=rows.reduce((s,r)=>s+r.before.total+r.after.total,0),total=[...a.runs,...b.runs].filter(r=>r.phase!=='warmup').length;
 return {rows,excluded:total-matched,message:rows.length?`${matched} comparable trials; ${total-matched} excluded for missing or different inputs, settings, providers or configurations. Server first PCM only; network and hosting conditions are uncontrolled.`:'No comparable trials. Inputs, task settings, provider configuration and architecture must match.'};
}
