"""Measured soma locations plus a clearly labelled read-only view of model state."""
import json
from functools import lru_cache
import numpy as np
from fly_model import ROOT


@lru_cache(maxsize=1)
def load_anatomy():
    data = np.load(ROOT/'data/anatomy_indices.npz', allow_pickle=False)
    meta = json.loads((ROOT/'data/anatomy_manifest.json').read_text(encoding='utf8'))
    codes = data['type_codes']
    return data['display'], codes, np.bincount(codes), meta


def snapshot(lab):
    display, codes, counts, meta = load_anatomy()
    with lab.lock:
        active = lab.mode in ('fly','rewired','untrained','disconnected','silenced')
        if active:
            x = lab.brain.x.detach().cpu().numpy().copy() if lab.brain.device == 'cuda' else lab.brain.x.copy()
        else:
            x = np.zeros(lab.brain.n, dtype=np.float32)
        means = np.bincount(codes, weights=np.abs(x), minlength=len(counts))/np.maximum(counts, 1)
        eligible = np.flatnonzero((counts >= 5) & (np.array(meta['type_names']) != 'untyped'))
        order = eligible[np.argsort(means[eligible])[-10:][::-1]]
        return {
            'mode': lab.mode, 'graph': lab.brain.graph, 'neural_controller': active,
            'paused': lab.paused, 'waiting_serve': lab.game.waiting_serve,
            'network_steps': lab.brain.ticks, 'actual_hz': lab.actual_hz,
            'activity': np.round(np.abs(x[display]).astype(float), 7).tolist(),
            'max_abs': float(np.max(np.abs(x))),
            'top_types': [{'name': meta['type_names'][i], 'n': int(counts[i]), 'mean_abs': float(means[i])} for i in order],
            'scope': 'Simulated dimensionless state magnitude; all model cells used for cell-type means; no measured brain activation.',
        }
