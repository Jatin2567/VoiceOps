import {TurnDetector,wavBytes} from '/shared/audio.mjs';
import {TurnState} from './turn-state.mjs';
import {microphoneConstraints,microphoneError,inputLevel,refreshDevices,stopMicrophoneCheck} from './microphone.mjs';
const turns=new TurnState();let transcriptSeen=false,connecting=false;
const $=id=>document.getElementById(id);
let ws=null,context=null,stream=null,node=null,source=null,sources=[],next=0,turn=null,pending=false,session=0,detector=null,sampleStage=0,sampleTimer=null;
function status(title,detail,state='idle'){if($('conversation-status').textContent!==title)$('conversation-status').textContent=title;if($('conversation-detail').textContent!==detail)$('conversation-detail').textContent=detail;$('voice-orb').dataset.state=state;}
function add(role,text){const entry=document.createElement('div');entry.className='utterance '+role;const label=document.createElement('small');label.textContent=role==='user'?'You':role==='tool'?'Verified tool outcome':'VoiceOps';entry.append(label,document.createTextNode(text));$('conversation-log').append(entry);}
function stopPlayback(){for(const s of sources){try{s.stop();}catch{}}sources=[];next=0;document.querySelectorAll('audio').forEach(a=>a.pause());}
function interrupt(){clearTimeout(sampleTimer);const id=turns.interrupt();if(ws?.readyState===1&&id)ws.send(JSON.stringify({type:'interrupt',utterance_id:id}));if(id)add('assistant','Reply interrupted. Your question stays in context.');turn=null;pending=false;stopPlayback();status('Listening…','Reply stopped. Speak your next request.','listening');}
function finish(message='Conversation ended.'){session++;connecting=false;turns.interrupt();inputLevel([0]);clearTimeout(sampleTimer);ws?.close();ws=null;stream?.getTracks().forEach(t=>t.stop());stream=null;node?.disconnect();source?.disconnect();stopPlayback();context?.close().catch(()=>{});context=null;turn=null;pending=false;sampleStage=0;window.voiceopsOtherBusy=false;$('start-conversation').hidden=false;$('end-conversation').hidden=true;$('interrupt-conversation').hidden=true;$('conversation-sample').disabled=false;status(message,'Start a conversation whenever you are ready.');for(const id of ['conversation-task','conversation-instruction','conversation-context','microphone-device'])$(id).disabled=false;}
function send(bytes){if(ws?.readyState!==1)return;if(pending||sources.length)interrupt();let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));pending=true;transcriptSeen=false;const utterance_id=turns.begin(crypto.randomUUID());ws.send(JSON.stringify({type:'audio',utterance_id,audio:btoa(binary)}));status('Thinking…','You can speak again to interrupt the reply.','thinking');}
function pcm(encoded){const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0)),buffer=context.createBuffer(1,bytes.length/2,16000),out=buffer.getChannelData(0),view=new DataView(bytes.buffer);for(let i=0;i<out.length;i++)out[i]=view.getInt16(i*2,true)/32768;const s=context.createBufferSource();s.buffer=buffer;s.connect(context.destination);next=Math.max(context.currentTime+.08,next);s.start(next);next+=buffer.duration;sources.push(s);s.onended=()=>{sources=sources.filter(v=>v!==s);if(!sources.length&&!pending){status('Listening…','Ask a follow-up or change the subject.','listening');}};status('Speaking…','Speak to interrupt, or choose Stop reply.','speaking');}
async function connect(microphone){
 if(window.voiceopsExperimentBusy||window.voiceopsOtherBusy)throw Error('Stop the active comparison, suite, or conversation first.');
 stopMicrophoneCheck();connecting=true;window.voiceopsOtherBusy=true;const stamp=++session;$('conversation-log').replaceChildren();$('conversation-sample').disabled=true;$('start-conversation').hidden=true;$('end-conversation').hidden=false;
 for(const id of ['conversation-task','conversation-instruction','conversation-context','microphone-device'])$(id).disabled=true;
 status('Connecting…',microphone?'Allow microphone access when prompted.':'Preparing two prerecorded voice turns.');
 context=new AudioContext({sampleRate:16000});const audioContext=context;await audioContext.resume();if(stamp!==session)return;if(audioContext.state!=='running')throw Error('Allow sound in your browser and try again.');
 if(microphone){
  const request=navigator.mediaDevices.getUserMedia(microphoneConstraints());let timer;
  request.then(s=>{if(stamp!==session)s.getTracks().forEach(t=>t.stop());},()=>{});
  let acquired;try{acquired=await Promise.race([request,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Microphone access timed out. Try Chrome or Edge.')),20000);})]);}finally{clearTimeout(timer);}
  if(stamp!==session){acquired.getTracks().forEach(t=>t.stop());return;}stream=acquired;refreshDevices().catch(()=>{});
  await audioContext.audioWorklet.addModule('/shared/capture.js');if(stamp!==session)return;
  detector=new TurnDetector(context.sampleRate,{silenceMs:800});node=new AudioWorkletNode(context,'voice-capture');source=context.createMediaStreamSource(stream);const gain=context.createGain();gain.gain.value=0;source.connect(node);node.connect(gain);gain.connect(context.destination);
  let interrupted=false;
  node.port.onmessage=e=>{if(stamp!==session||ws?.readyState!==1)return;inputLevel(e.data);const audio=detector.push(e.data);if(detector.voiced>=context.sampleRate*.22&&!interrupted){interrupted=true;if(pending||sources.length)interrupt();status('Listening…','A short pause sends your request.','listening');}if(audio){interrupted=false;send(wavBytes(audio,context.sampleRate));}else if(!detector.active)interrupted=false;};
 }
 if(stamp!==session)return;
 ws=new WebSocket((location.protocol==='https:'?'wss:':'ws:')+'//'+location.host+'/conversation/ws');
 const readyTimer=setTimeout(()=>{if(stamp===session)finish('Connection timed out. Please retry.');},20000);
 ws.onopen=()=>ws.send(JSON.stringify({spec:{task:$('conversation-task').value,instruction:$('conversation-instruction').value,context:$('conversation-context').value}}));
 ws.onmessage=async event=>{if(stamp!==session)return;try{const m=JSON.parse(event.data);
  if(m.type==='ready'){connecting=false;clearTimeout(readyTimer);$('interrupt-conversation').hidden=false;status('Listening…',microphone?'Speak naturally. A short pause sends your request.':'Playing a sample request through live providers.','listening');if(!microphone){sampleStage=1;const r=await fetch('/sample.wav');if(stamp===session)send(new Uint8Array(await r.arrayBuffer()));}}
  if(m.type==='turn_start'&&turns.accepts(m)){turn=m.turn_id;pending=true;}
  if(m.type==='audio'&&turns.accepts(m))pcm(m.pcm);
  if(m.type==='transcript'&&turns.accepts(m)){add('user',m.text);transcriptSeen=true;}
  if(m.type==='result'&&turns.accepts(m)){pending=false;if(!transcriptSeen)add('user',m.transcript||'No transcript');for(const tool of m.tools||[])add('tool',`Simulation only · ${tool.action} · ${tool.status} · No external effect`);add('assistant',m.error||m.response||'No reply');if(m.evaluation?.status==='fail')add('assistant','Supplied criteria did not pass. Review the response.');if(!sources.length)status('Listening…','Ask a follow-up.','listening');
   if(sampleStage===1){sampleStage=2;sampleTimer=setTimeout(async()=>{const r=await fetch('/followup.wav');if(stamp===session)send(new Uint8Array(await r.arrayBuffer()));},Math.max(0,next-context.currentTime)*1000+300);}else if(sampleStage===2){sampleStage=3;sampleTimer=setTimeout(()=>{if(stamp===session)finish('Sample conversation complete.');},Math.max(0,next-context.currentTime)*1000+300);}}
  if(m.type==='error'||m.type==='complete'){clearTimeout(readyTimer);finish(m.message);}
 }catch{clearTimeout(readyTimer);finish('Audio or connection failed. Please reconnect.');}};
 ws.onerror=()=>{clearTimeout(readyTimer);if(stamp===session)finish('Could not connect. Please retry.');};ws.onclose=()=>{clearTimeout(readyTimer);if(stamp===session)finish('Conversation disconnected.');};
}
function start(microphone){if(window.voiceopsExperimentBusy||window.voiceopsOtherBusy){status('Another run is active.','Stop the comparison, suite, or current conversation first.');return;}const expected=session+1;connect(microphone).catch(e=>{if(session===expected)finish(microphoneError(e));});}
$('start-conversation').onclick=()=>start(true);$('conversation-sample').onclick=()=>start(false);$('end-conversation').onclick=()=>finish();$('interrupt-conversation').onclick=interrupt;window.addEventListener('pagehide',()=>finish());
document.querySelectorAll('[data-view]').forEach(button=>button.addEventListener('click',()=>{if(button.dataset.view!=='conversation'&&(ws||stream||connecting))finish('Conversation ended when you left this workspace.');}));
document.addEventListener('visibilitychange',()=>{if(document.hidden&&(ws||stream||connecting))finish('Conversation ended while this tab was hidden.');});
