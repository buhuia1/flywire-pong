"""Equal-data calibration and fixed-serve, held-out evaluation at three difficulties."""
import argparse
import json
import time
import numpy as np
from fly_model import FlyNetwork, Readout, ROOT
from pong import Pong, DIFFICULTIES

MODES = ['fly', 'rewired', 'direct', 'untrained', 'disconnected', 'silenced', 'random', 'rule']
NEURAL = {'fly', 'rewired', 'untrained', 'disconnected', 'silenced'}


def demonstration_data(seed=42, static_samples=1600, dynamic_steps=4000):
    rng = np.random.default_rng(seed)
    observations, targets, resets, repeats = [], [], [], []
    difficulties = list(DIFFICULTIES)
    for i in range(static_samples):
        obs = rng.uniform(-1, 1, 5).astype(np.float32)
        speed = DIFFICULTIES[difficulties[i % 3]]['speed']
        angle = rng.uniform(-.96, .96)
        obs[3] = rng.choice([-1, 1])*speed*np.cos(angle)/.6
        obs[4] = speed*np.sin(angle)/.6
        observations.append(obs)
        targets.append((obs[0]-obs[1])*.5*9)
        resets.append(True)
        repeats.append(4)
    game = None
    for j in range(dynamic_steps):
        reset = j % 200 == 0
        if reset:
            game = Pong(101+j, difficulty=difficulties[(j//200) % 3])
            game.paddle = float(rng.uniform(.15, .85))
        obs = game.observation()
        observations.append(obs)
        targets.append((game.y-game.paddle)*9)
        resets.append(reset)
        repeats.append(1)
        game.step(game.teacher()+float(rng.normal(0, .3)))
    return np.array(observations), np.array(targets), np.array(resets), np.array(repeats)


def train_all(brains):
    observations, targets, resets, repeats = demonstration_data()
    output = ROOT/'results'
    np.savez_compressed(output/'training_samples.npz', observations=observations, targets=targets,
                        resets=resets, repeats=repeats)
    models, times = {}, {}
    for name, brain in brains.items():
        started = time.perf_counter()
        features = []
        for obs, reset, count in zip(observations, resets, repeats):
            if reset:
                brain.reset()
            for _ in range(int(count)):
                values = brain.advance(obs)
            features.append(values.copy())
        models[name] = Readout.fit(features, targets, ridge=.2)
        models[name].save(output/('pong_readout.npz' if name == 'real' else 'rewired_readout.npz'))
        times[name] = time.perf_counter()-started
        print(f'Calibrated {name}: {times[name]:.1f} s', flush=True)
    models['direct'] = Readout.fit(observations, targets, ridge=.2)
    models['direct'].save(output/'direct_readout.npz')
    metadata = {'version': 2, 'seed': 42, 'static_samples': 1600, 'dynamic_steps': 4000,
                'seconds_by_model': times, 'seconds': sum(times.values()),
                'target': '9 * (ball_y - paddle_y); same demonstration observations for all trained controllers',
                'rule': 'supervised ridge regression, ridge=0.2, standardized features',
                'recurrent_weights_trained': False, 'online_learning': False,
                'same_training_data_for_real_rewired_direct': True,
                'same_readout_selection_rule_for_real_rewired': True,
                'training_difficulties': list(DIFFICULTIES),
                'training_game_seeds': list(range(101, 4101, 200)),
                'brain_config': brains['real'].config()}
    (output/'training.json').write_text(json.dumps(metadata, indent=2), encoding='utf8')
    return models


def load_models():
    return {name: Readout.load(ROOT/'results'/file) for name, file in
            [('real', 'pong_readout.npz'), ('rewired', 'rewired_readout.npz'), ('direct', 'direct_readout.npz')]}


def evaluate(brains, models, seeds=(9101, 9102, 9103), encounters=35):
    started = time.perf_counter()
    untrained = Readout(np.random.default_rng(777).normal(0, .3, 193))
    profiles = []
    for difficulty in DIFFICULTIES:
        results = []
        for mode in MODES:
            runs = []
            for seed in seeds:
                # Every controller sees exactly the same independent serves and starts centered.
                trial_seeds = np.random.default_rng(seed).integers(100000, 2147483647, size=encounters)
                hits, misses, ticks, errors = 0, 0, 0, []
                brain = brains['rewired' if mode == 'rewired' else 'real']
                for trial_seed in trial_seeds:
                    p = Pong(int(trial_seed), difficulty=difficulty)
                    rng = np.random.default_rng(int(trial_seed)+123)
                    if mode in NEURAL:
                        brain.reset()
                    for _ in range(180):
                        obs = p.observation()
                        if mode in NEURAL:
                            f = brain.advance(obs, disconnected=mode == 'disconnected', silence_input=mode == 'silenced')
                            decoder = untrained if mode == 'untrained' else models['rewired' if mode == 'rewired' else 'real']
                            action = decoder.predict(f)
                        elif mode == 'direct':
                            action = models['direct'].predict(obs)
                        elif mode == 'random':
                            action = float(rng.choice([-1, 0, 1]))
                        else:
                            action = p.teacher()
                        event = p.step(action)
                        ticks += 1
                        if event in ('hit', 'miss'):
                            hits += int(event == 'hit')
                            misses += int(event == 'miss')
                            break
                    else:
                        raise AssertionError('A fixed serve did not reach the left paddle')
                runs.append({'seed': seed, 'hits': hits, 'misses': misses,
                             'hit_rate': hits/encounters, 'ticks': ticks})
            rates = [row['hit_rate'] for row in runs]
            results.append({'mode': mode, 'mean_hit_rate': float(np.mean(rates)),
                            'min_hit_rate': min(rates), 'max_hit_rate': max(rates), 'runs': runs})
            print(f'{difficulty:6s} {mode:12s} {np.mean(rates):.1%}', flush=True)
        profiles.append({'difficulty': difficulty, 'results': results})
    report = {'version': 2, 'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'task': 'fixed independent left-paddle serves; not human-match scores or a learning curve',
              'seeds': list(seeds), 'encounters_per_seed': encounters, 'difficulties': DIFFICULTIES,
              'profiles': profiles, 'results': profiles[1]['results'], 'wall_seconds': time.perf_counter()-started,
              'brain_config': brains['real'].config(),
              'initial_serve_control': 'Exact same trial seeds and centered paddle per serve; reset neural state per trial.',
              'interpretation': 'One source-shuffled graph with separately calibrated readout. No online learning; no biological superiority claim.'}
    (ROOT/'results/benchmark.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', default='auto', choices=['auto', 'cpu', 'cuda'])
    parser.add_argument('--skip-train', action='store_true')
    parser.add_argument('--encounters', type=int, default=35)
    args = parser.parse_args()
    brains = {graph: FlyNetwork(args.device, graph=graph) for graph in ('real', 'rewired')}
    models = load_models() if args.skip_train else train_all(brains)
    evaluate(brains, models, encounters=args.encounters)


if __name__ == '__main__':
    main()
