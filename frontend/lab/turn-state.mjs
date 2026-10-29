// Client identity exists before the server acknowledgement, so cancellation wins
// over late acknowledgements, audio and results from any earlier utterance.
export class TurnState {
  active = null;
  begin(id) { this.active = id; return id; }
  accepts(packet) { return this.active !== null && packet.utterance_id === this.active; }
  interrupt() { const id = this.active; this.active = null; return id; }
}
