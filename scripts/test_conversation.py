"""Opt-in live transport smoke: follow-up context, cancellation, then recovery."""
import argparse
import asyncio
import base64
import json
import time
from pathlib import Path
import websockets


async def main(args):
    root = Path(__file__).resolve().parents[1] / 'frontend/lab'
    report = {'scope': 'Prerecorded voice with live providers; no physical microphone or acoustic measurement', 'turns': []}
    async with websockets.connect(args.url, max_size=2000000, open_timeout=30) as ws:
        await ws.send(json.dumps({'spec': {'instruction': 'Keep replies brief, clear and conversational.'}}))
        assert json.loads(await ws.recv())['type'] == 'ready'
        for index, name in enumerate(['sample', 'followup', 'sample', 'followup', 'extraction'], 1):
            await ws.send(json.dumps({'type':'audio','utterance_id':f'live-{index}','audio':base64.b64encode((root/(name+'.wav')).read_bytes()).decode()}))
            cancelled_at, packets = None, 0
            while True:
                m = json.loads(await asyncio.wait_for(ws.recv(), 75))
                if m['type'] == 'error':
                    raise RuntimeError(m['message'])
                if m['type'] == 'audio':
                    packets += 1
                if index == 3 and m['type'] == 'audio' and cancelled_at is None:
                    cancelled_at = time.perf_counter()
                    await ws.send(json.dumps({'type':'interrupt','utterance_id':'live-3'}))
                if m['type'] == 'interrupted':
                    assert index == 3
                    report['interruption_phase'] = 'after first PCM packet';report['cancelled_audio_packets'] = packets
                    report['cancellation_ack_ms'] = round((time.perf_counter()-cancelled_at)*1000)
                    break
                if m['type'] == 'result':
                    assert m['turn_id'] == index and m['status'] == 'completed' and packets > 0, (m.get('turn_id'), m.get('status'), m.get('error'), packets)
                    report['turns'].append({**m,'audio_packets':packets})
                    print(index, m['transcript'], '→', m['response'], flush=True)
                    break
    assert len(report['turns']) == 4 and 'cancellation_ack_ms' in report
    assert any(word in report['turns'][2]['response'].lower() for word in ('rainbow', 'light', 'water', 'color')), 'Interrupted question lost from context'
    assert report['turns'][3]['tools'] and all(t['external_effect'] is False for t in report['turns'][3]['tools'])
    assert 'No real' in report['turns'][3]['response']
    Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Follow-up, provider cancellation, and next-turn recovery completed.', flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--url',default='ws://127.0.0.1:8511/conversation/ws')
    p.add_argument('--output',default='.venv/conversation-live.json')
    asyncio.run(main(p.parse_args()))
