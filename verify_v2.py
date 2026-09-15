"""Behavioral tests for player ownership, shot direction, harder tasks and graph isolation."""
import json
import time
import numpy as np
from fly_model import FlyNetwork, ROOT
from pong import Pong, RIGHT_X, PADDLE_X, BALL_RADIUS, DIFFICULTIES
from server import Lab, validate_command


def main():
    checks = {}
    p = Pong(123, 'normal', 'human')
    checks['human_game_waits_for_serve'] = p.waiting_serve and p.vx == 0
    p.set_player(y=.8, aim=-35)
    for _ in range(5):
        p.step(0)
    checks['right_control_does_not_move_left'] = abs(p.right_paddle-.8)<1e-6 and p.paddle == .5
    p.serve()
    checks['serve_angle_goes_up_and_left'] = p.vx < 0 and p.vy < 0 and not p.waiting_serve
    p.x, p.y, p.vx, p.vy = RIGHT_X-BALL_RADIUS-.001, p.right_paddle, p.speed, 0.
    p.set_player(aim=40)
    event = p.step(0)
    checks['human_return_angle_changes_direction'] = event == 'human_hit' and p.vx < 0 and p.vy > 0
    p.x, p.y, p.vx, p.vy = PADDLE_X+BALL_RADIUS+.001, p.paddle, -p.speed, 0.
    checks['left_paddle_returns_automatically'] = p.step(0) == 'hit' and p.vx > 0
    p.x, p.y, p.vx, p.vy = RIGHT_X-BALL_RADIUS-.001, .05, p.speed, 0.
    checks['human_miss_requires_new_serve'] = p.step(0) == 'human_miss' and p.waiting_serve
    checks['difficulty_speed_increases'] = DIFFICULTIES['easy']['speed'] < DIFFICULTIES['normal']['speed'] < DIFFICULTIES['hard']['speed']
    checks['difficulty_left_paddle_shrinks'] = DIFFICULTIES['easy']['paddle_half'] > DIFFICULTIES['normal']['paddle_half'] > DIFFICULTIES['hard']['paddle_half']
    p1, p2 = Pong(432, 'hard'), Pong(432, 'hard')
    for i in range(150):
        p1.step(np.sin(i));p2.step(np.sin(i))
    checks['deterministic_hard_game'] = p1.snapshot() == p2.snapshot()
    rejected = 0
    for command in [{'player_y':2}, {'aim':60}, {'difficulty':'invalid'}, {'serve':'yes'}, {'player_y':float('nan')}]:
        try:validate_command(command)
        except ValueError:rejected += 1
    checks['invalid_controls_rejected'] = rejected == 5
    brains = {name:FlyNetwork(graph=name) for name in ('real','rewired')}
    obs = np.array([.5,-.2,.6,-1.1,.4],dtype=np.float32)
    a, b = brains['real'].clone_state(), brains['real'].clone_state()
    before = b.x.clone() if b.device == 'cuda' else b.x.copy()
    a.advance(obs)
    unchanged = bool((b.x == before).all().item()) if b.device == 'cuda' else np.array_equal(b.x,before)
    checks['clones_share_only_immutable_weights'] = a.W is b.W and unchanged
    ref_path = ROOT/'results/cpu_backend_reference.npz'
    if ref_path.exists():
        reference = np.load(ref_path)
        for name, brain in brains.items():
            brain.reset()
            for _ in range(6):actual = brain.advance(obs)
            checks[name+'_cpu_gpu_agree'] = bool(np.allclose(actual,reference[name],atol=2e-6,rtol=2e-5))
    lab = Lab('auto',brains={name:brain.clone_state() for name,brain in brains.items()})
    try:
        lab.control({'paused':True,'player_y':.75,'aim':25})
        s = lab.snapshot()
        checks['player_command_preserves_fly_controller'] = s['mode']=='fly' and s['game']['paddle']==.5 and s['game']['right_target']==.75
        lab.control({'mode':'rewired','difficulty':'hard','opponent':'wall'})
        s = lab.snapshot()
        checks['rewired_mode_uses_rewired_matrix'] = s['graph']=='rewired' and lab.brain is lab.brains['rewired']
        lab.control({'reset':True})
        checks['reset_clears_action_and_activity'] = lab.action==0 and not np.any(lab.features)
    finally:
        lab.stop.set()
        lab.thread.join(timeout=3)
    report = {'version':2,'checks':checks,'passed':all(checks.values())}
    (ROOT/'results/verification_v2.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2))
    assert report['passed']


if __name__ == '__main__':
    main()
