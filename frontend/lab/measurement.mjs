// Browser clocks describe scheduling and delivery, never acoustic measurements.
export class PlaybackClock {
  constructor(lead=.08){this.lead=lead;this.reset();}
  reset(){this.next=0;this.first=null;this.firstReceived=null;this.gaps=0;this.gapMs=0;this.latePackets=0;this.chunks=0;}
  packet(audioNow,performanceNow,requestAt,frames,rate=16000){
    const start=Math.max(audioNow+this.lead,this.next);
    if(this.chunks&&start>this.next+1e-6){this.gaps++;this.gapMs+=(start-this.next)*1000;}
    if(this.chunks&&audioNow>this.next)this.latePackets++;
    if(this.first===null){this.firstReceived=performanceNow-requestAt;this.first=this.firstReceived+(start-audioNow)*1000;}
    this.chunks++;this.next=start+frames/rate;return start;
  }
  metrics(){return {first_pcm_received_ms:this.firstReceived,scheduled_playback_ms:this.first,scheduled_gap_count:this.gaps,scheduled_gap_ms:Math.round(this.gapMs),late_packet_count:this.latePackets,pcm_chunks:this.chunks,playback_lead_ms:this.lead*1000};}
}
export function recoverySnapshot(history){return history.map(e=>({...e,runs:e.runs.map(({audio_url,...run})=>run)}));}
