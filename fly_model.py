"""Actual FlyWire topology with an explicitly engineered rate-model dynamical system."""
from pathlib import Path
import copy
import json
import time
import numpy as np

ROOT = Path(__file__).resolve().parent


class FlyNetwork:
    def __init__(self, device='auto', seed=17, gain=0.9, leak=0.8, substeps=2, graph='real'):
        self.seed, self.gain, self.leak, self.substeps = seed, gain, leak, substeps
        self.manifest = json.loads((ROOT/'data/manifest.json').read_text(encoding='utf8'))
        if graph not in ('real', 'rewired'):
            raise ValueError('unknown graph')
        self.graph = graph
        z = np.load(ROOT/('data/flywire_graph.npz' if graph == 'real' else 'data/rewired_graph.npz'), allow_pickle=False)
        self.n = len(z['neuron_ids'])
        self.ids = z['neuron_ids']
        self.input_indices, self.readout_indices = z['input_indices'], z['readout_indices']
        assert not np.intersect1d(self.input_indices, self.readout_indices).size
        rng = np.random.default_rng(seed)
        self.encoder = rng.normal(0, .65, (len(self.input_indices), 5)).astype(np.float32)
        self.encoder_bias = rng.uniform(-.25, .25, len(self.input_indices)).astype(np.float32)
        self.device = 'cpu'
        self.torch = None
        if device != 'cpu':
            try:
                import torch
                if torch.cuda.is_available():
                    self.torch = torch
                    self.device = 'cuda'
            except ImportError:
                pass
        if device == 'cuda' and self.device != 'cuda':
            raise RuntimeError('CUDA requested but not available in this Python runtime')
        if self.device == 'cuda':
            t = self.torch
            t.set_num_threads(4)
            self.W = t.sparse_csr_tensor(t.as_tensor(z['indptr'].astype(np.int64),device='cuda'),
                t.as_tensor(z['indices'].astype(np.int64),device='cuda'),
                t.as_tensor(z['data'],device='cuda'),size=(self.n,self.n),device='cuda')
            self.x = t.zeros(self.n, device='cuda')
            self.in_idx = t.as_tensor(self.input_indices.astype(np.int64),device='cuda')
            self.out_idx = t.as_tensor(self.readout_indices.astype(np.int64),device='cuda')
            self.enc = t.as_tensor(self.encoder, device='cuda')
            self.enc_bias = t.as_tensor(self.encoder_bias, device='cuda')
        else:
            from scipy.sparse import csr_matrix
            self.W = csr_matrix((z['data'],z['indices'],z['indptr']),shape=(self.n,self.n))
            self.x = np.zeros(self.n,dtype=np.float32)
        self.ticks = 0
        self.last_ms = 0
        self.last_features = np.zeros(len(self.readout_indices),dtype=np.float32)

    def reset(self):
        if self.device == 'cuda':
            self.x.zero_()
        else:
            self.x.fill(0)
        self.ticks=0
        self.last_features.fill(0)

    def clone_state(self):
        """New dynamic state sharing only immutable matrix/encoding buffers."""
        clone = copy.copy(self)
        clone.x = self.torch.zeros_like(self.x) if self.device == 'cuda' else np.zeros_like(self.x)
        clone.last_features = np.zeros_like(self.last_features)
        clone.ticks, clone.last_ms = 0, 0
        return clone

    def advance(self, observation, disconnected=False, silence_input=False):
        """Decoder receives only neuronal states, never game coordinates."""
        start = time.perf_counter()
        if self.device == 'cuda':
            t = self.torch
            obs = t.as_tensor(observation,dtype=t.float32,device='cuda')
            drive = self.enc @ obs + self.enc_bias
            if silence_input:
                drive.zero_()
            with t.no_grad():
                for _ in range(self.substeps):
                    s = t.zeros_like(self.x) if disconnected else t.mv(self.W,self.x)*self.gain
                    s[self.in_idx] += drive
                    self.x = (1-self.leak)*self.x + self.leak*t.tanh(s)
                features = self.x[self.out_idx].cpu().numpy()
        else:
            drive = self.encoder @ np.asarray(observation,dtype=np.float32)+self.encoder_bias
            if silence_input:
                drive *= 0
            for _ in range(self.substeps):
                s = np.zeros_like(self.x) if disconnected else self.W @ self.x*self.gain
                s[self.input_indices] += drive
                self.x = (1-self.leak)*self.x + self.leak*np.tanh(s)
            features = self.x[self.readout_indices].copy()
        self.last_features=features.copy()
        self.ticks+=self.substeps
        self.last_ms=(time.perf_counter()-start)*1000
        return features

    def config(self):
        return {'seed':self.seed,'gain':self.gain,'leak':self.leak,'substeps':self.substeps,
                'neurons':self.n,'edges':self.manifest['effective_edges'],
                'device':self.device,'observed_neurons':len(self.readout_indices),'graph':self.graph}


class Readout:
    def __init__(self, weights=None):
        self.weights=weights

    def predict(self, features):
        if self.weights is None:
            return 0.0
        return float(np.clip(np.append(features,1.0) @ self.weights,-1,1))

    @classmethod
    def fit(cls, X, y, ridge=.02):
        X=np.asarray(X,dtype=np.float64)
        mean=X.mean(axis=0)
        scale=np.maximum(X.std(axis=0),1e-6)
        X=np.column_stack(((X-mean)/scale,np.ones(len(X))))
        reg=np.eye(X.shape[1])*ridge
        reg[-1,-1]=1e-8
        weights=np.linalg.solve(X.T@X+reg,X.T@np.asarray(y))
        return cls(np.append(weights[:-1]/scale,weights[-1]-np.dot(mean/scale,weights[:-1])))

    def save(self,path):
        np.savez(path,weights=self.weights)

    @classmethod
    def load(cls,path):
        return cls(np.load(path,allow_pickle=False)['weights'])
