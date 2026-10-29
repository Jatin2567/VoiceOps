import {TurnDetector,wavBytes} from './audio.mjs';
const $=id=>document.getElementById(id), uuid=()=>crypto.randomUUID();
const send=(type,data={})=>parent.postMessage({isStreamlitMessage:true,type,...data},'*');
const fit=()=>send('streamlit:setFrameHeight',{height:Math.ceil(document.body.getBoundingClientRect().height)+8});
async function bounded(promise,ms){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new DOMException('Permission or audio setup timed out','TimeoutError')),ms);})]);}finally{clearTimeout(timer);}}
let args={},session=null,ctx=null,stream=null,capture=null,source=null,playback=null;
let detector=null,running=false,muted=false,busy=false,mode='mic',demoIndex=0,pending=null,watchdog=null,idle=null,generation=0;
const seen=new Set();
const emit=(kind,fields={})=>send('streamlit:setComponentValue',{value:{event_id:uuid(),kind,...fields},dataType:'json'});
function state(name,title,detail){document.body.dataset.state=name;$('status').textContent=title;$('detail').textContent=detail;}
function controls(){
  $('start').hidden=running;$('controls').hidden=!running;$('demo').hidden=running;
  $('start').disabled=args.online===false;$('demo').disabled=args.online===false;
  $('pause').hidden=mode==='demo';$('pause').textContent=muted?'Unmute microphone':'Mute microphone';
}
async function audioContext(){if(!ctx || ctx.state==='closed')ctx=new AudioContext({sampleRate:16000});await bounded(ctx.resume(),5000);return ctx;}
function stopMedia(){
  generation++;clearTimeout(watchdog);clearTimeout(idle);
  if(playback){playback.onended=null;try{playback.stop();}catch{}playback=null;}
  if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}
  capture?.disconnect();source?.disconnect();capture=null;source=null;
  if(ctx){ctx.close().catch(()=>{});ctx=null;}
  detector=null;$('level').style.width='0';
}
function fail(message,retry=false){
  clearTimeout(watchdog);busy=false;
  if(stream)stream.getAudioTracks().forEach(t=>t.enabled=false);
  state('error','Let’s pause here.',message);$('retry').hidden=!retry;controls();
}
function arm(){
  if(!running)return;
  busy=false;pending=null;$('retry').hidden=true;$('play').hidden=true;
  detector?.reset();
  if(mode==='demo'){demoNext();return;}
  if(stream)stream.getAudioTracks().forEach(t=>t.enabled=!muted);
  state(muted?'muted':'listening',muted?'Microphone muted':'I’m listening.',muted?'Unmute whenever you’re ready.':'Speak naturally. A short pause sends your turn automatically.');
  clearTimeout(idle);idle=setTimeout(()=>{muted=true;arm();state('muted','Taking a break.','Microphone muted after five minutes without a turn.');},300000);
  controls();
}
function acceptSamples(samples,rate){
  if(!running || busy || muted || document.body.dataset.state!=='listening')return;
  const level=Math.sqrt(samples.reduce((n,v)=>n+v*v,0)/samples.length);
  $('level').style.width=Math.min(100,level*1300)+'%';
  const turn=detector.push(samples);
  if(turn){
    clearTimeout(idle);busy=true;
    if(stream)stream.getAudioTracks().forEach(t=>t.enabled=false);
    let binary='';for(const byte of wavBytes(turn,rate))binary+=String.fromCharCode(byte);
    pending={turn_id:uuid(),audio_base64:btoa(binary)};submit();
  }
}
function submit(){
  busy=true;$('retry').hidden=true;state('thinking','Thinking it through.','Checking the request and preparing a spoken reply…');
  emit('turn',pending);clearTimeout(watchdog);
  watchdog=setTimeout(()=>fail('The connection took too long. Retry this same turn to retrieve its result safely.',true),85000);
}
async function start(demo=false){
  let stamp;
  try{
    stopMedia();mode=demo?'demo':'mic';muted=false;busy=true;running=true;demoIndex=0;pending=null;controls();
    stamp=generation;
    state('connecting','Opening your call…',demo?'Sample voices use the same automatic turn detection and live providers.':'Allow microphone access when your browser asks.');
    await audioContext();
    if(stamp!==generation)return;
    if(!demo){
      const permission=navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      permission.then(s=>{if(stamp!==generation)s.getTracks().forEach(t=>t.stop());},()=>{});
      const acquired=await bounded(permission,20000);
      if(stamp!==generation){acquired.getTracks().forEach(t=>t.stop());return;}
      stream=acquired;
      await ctx.audioWorklet.addModule(new URL('capture.js',import.meta.url));
      if(stamp!==generation)return;
      source=ctx.createMediaStreamSource(stream);capture=new AudioWorkletNode(ctx,'voice-capture');
      detector=new TurnDetector(ctx.sampleRate);
      capture.port.onmessage=e=>acceptSamples(e.data,ctx.sampleRate);
      const silent=ctx.createGain();silent.gain.value=0;source.connect(capture);capture.connect(silent);silent.connect(ctx.destination);
      stream.getAudioTracks().forEach(t=>{t.onended=()=>{if(running)fail('Microphone disconnected. End the call and reconnect your device.');};});
    }
    emit('start',{fresh:demo});
    watchdog=setTimeout(()=>fail('The call could not open. End it and try again.'),15000);
  }catch(e){
    if(stamp!==generation)return;
    stopMedia();running=false;controls();
    state('error','Microphone unavailable.',e.name==='NotAllowedError'?'Allow microphone permission, then try Start call again.':e.name==='TimeoutError'?'Microphone or audio permission did not complete. Open this app in Chrome or Edge, allow microphone access, and try again.':'Check your microphone and browser audio support, then try again.');
  }
}
async function playBuffer(buffer){
  await audioContext();
  return new Promise(resolve=>{playback=ctx.createBufferSource();playback.buffer=buffer;playback.connect(ctx.destination);playback.onended=()=>{playback=null;resolve();};playback.start();});
}
async function reply(result){
  clearTimeout(watchdog);const stamp=generation;
  if(result.error){fail(result.error,Boolean(result.retryable&&pending));return;}
  if(result.status!=='completed'||!result.audio_base64){fail(result.error_message||'No spoken reply was available. Check Booking activity before trying again.');return;}
  try{
    busy=true;state('speaking','Your assistant is speaking.', 'Listening resumes automatically when the reply ends.');
    const bytes=Uint8Array.from(atob(result.audio_base64),c=>c.charCodeAt(0));
    const buffer=await ctx.decodeAudioData(bytes.buffer);
    if(ctx.state!=='running'){
      $('play').hidden=false;$('play').onclick=async()=>{await playBuffer(buffer);if(stamp===generation)arm();};
      state('paused','Tap to hear the reply.','Your browser paused audio playback. Continue once to resume the call.');return;
    }
    await playBuffer(buffer);if(stamp===generation)arm();
  }catch{fail('Audio playback failed. End the call and check your output device.');}
}
async function demoNext(){
  const files=['demo-booking.wav','demo-cancel.wav'];
  if(demoIndex>=files.length){state('complete','Sample conversation complete.','Booking and cancellation finished. Review the transcript and booking activity below.');busy=false;return;}
  const stamp=generation;
  try{
    busy=true;state('demo','Sample caller is speaking.',demoIndex===0?'A fictional booking request.':'A follow-up cancellation using the same conversation.');
    const response=await fetch(new URL(files[demoIndex++],import.meta.url));if(!response.ok)throw Error();
    const buffer=await ctx.decodeAudioData(await response.arrayBuffer());
    await playBuffer(buffer);if(stamp!==generation)return;
    detector=new TurnDetector(buffer.sampleRate);busy=false;state('listening','Detecting the end of the turn…','The sample uses the same pause detector as microphone audio.');
    const pcm=buffer.getChannelData(0);
    for(let i=0;i<pcm.length && !busy;i+=1024)acceptSamples(pcm.subarray(i,i+1024),buffer.sampleRate);
    for(let i=0;i<2*buffer.sampleRate && !busy;i+=1024)acceptSamples(new Float32Array(1024),buffer.sampleRate);
    if(!busy)throw Error();
  }catch{fail('The sample audio could not be played. End the call and try again.');}
}
$('start').onclick=()=>start(false);$('demo').onclick=()=>start(true);
$('pause').onclick=()=>{muted=!muted;if(!busy)arm();else controls();};
$('retry').onclick=()=>submit();
$('end').onclick=()=>{running=false;busy=false;stopMedia();$('retry').hidden=true;$('play').hidden=true;controls();state('idle','Call ended.','Your microphone is off. Any action already processing may still finish.');emit('end');};
window.addEventListener('message',e=>{
  if(e.source!==parent||e.data.type!=='streamlit:render')return;
  args=e.data.args||{};session=args.session_id;controls();
  const result=args.result;
  if(result && !seen.has(result.event_id)){
    seen.add(result.event_id);
    if(running){if(result.kind==='start'&&!result.error){clearTimeout(watchdog);arm();}else if(result.kind==='turn'||result.error)reply(result);}
  }
  fit();
});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&running&&mode==='mic'){muted=true;if(stream)stream.getAudioTracks().forEach(t=>t.enabled=false);if(!busy)arm();}});
window.addEventListener('pagehide',()=>{running=false;stopMedia();});
new ResizeObserver(fit).observe(document.body);
send('streamlit:componentReady',{apiVersion:1});fit();
