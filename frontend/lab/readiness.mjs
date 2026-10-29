const $=id=>document.getElementById(id);
let snapshot=null;
export async function refreshReadiness(){
 $('readiness').textContent='Connecting to server…';
 try{const r=await fetch('/api/readiness',{signal:AbortSignal.timeout(15000),cache:'no-store'});if(!r.ok)throw Error();snapshot=await r.json();$('readiness').textContent=snapshot.configured?(snapshot.capacity_available?'● Server ready':'● Demo slots busy'):'Setup needed';updateAllowance();}
 catch{$('readiness').textContent='Connection unavailable';$('allowance').textContent='Could not check allowance. Refresh connection status to retry.';snapshot=null;}
 return snapshot;
}
export function updateAllowance(){
 const modes=document.querySelectorAll('.mode input:checked').length,count=modes*(Number($('repeats').value)+Number($('warmup').checked));
 $('allowance').textContent=`Planned: ${count} trials`+(snapshot?` · ${snapshot.quota.available_trials} available · ${snapshot.quota.starts_remaining} starts available this window. Snapshot; admission is checked at start. ${snapshot.configured?'Providers are verified during use.':'Server configuration needed.'}`:' · Allowance not yet checked.');
}
$('retry-ready').onclick=refreshReadiness;
document.querySelectorAll('.mode input,#repeats,#warmup').forEach(e=>e.addEventListener('change',updateAllowance));
refreshReadiness();
