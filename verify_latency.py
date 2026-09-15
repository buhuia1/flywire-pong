"""Check mouse control semantics and the minimal input endpoint."""
import json
import time
from pathlib import Path
from urllib.request import urlopen, Request
from pong import Pong, RIGHT_X, BALL_RADIUS, DT

ROOT = Path(__file__).resolve().parent


def main():
    g = Pong(123, 'normal', 'human')
    g.set_player(.85, 20)
    assert g.right_paddle == .85 and g.y == .85 and g.waiting_serve
    g.serve()
    # Late, valid human positioning is applied before the next collision check.
    g.x = RIGHT_X-BALL_RADIUS-.01
    g.y, g.vx, g.vy = .2, .75, 0
    g.set_player(.2)
    assert g.step(0) == 'human_hit'
    assert g.right_hits == 1 and g.vx < 0
    base = 'http://127.0.0.1:8741'
    times, sizes = [], []
    for i in range(40):
        y = .2 if i % 2 else .8
        start = time.perf_counter()
        req = Request(base+'/api/input', json.dumps({'player_y':y,'aim':-20}).encode(), {'Content-Type':'application/json'})
        with urlopen(req) as response: payload = response.read()
        times.append((time.perf_counter()-start)*1000); sizes.append(len(payload))
        assert json.loads(payload) == {'ok':True}
        with urlopen(base+'/api/state') as response: state = json.load(response)
        assert state['game']['right_paddle'] == y
    with urlopen(Request(base+'/api/input',b'{"player_y":0.5}',{'Content-Type':'application/json'})) as response: response.read()
    result = {'direct_human_position':True,'right_collision_uses_latest_input':True,
              'inputs_verified':len(times),'input_reply_bytes':max(sizes),
              'rtt_median_ms':sorted(times)[len(times)//2], 'rtt_p95_ms':sorted(times)[int(len(times)*.95)-1]}
    (ROOT/'results/latency-after.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__ == '__main__': main()
