"""Build a signed sparse graph from the original Shiu v783 files; no invented edges."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def prepare():
    cells = pd.read_csv(DATA / 'Completeness_783.csv').iloc[:, 0].to_numpy(np.int64)
    edge = pd.read_parquet(DATA / 'Connectivity_783.parquet')
    pre = edge['Presynaptic_Index'].to_numpy(np.int32)
    post = edge['Postsynaptic_Index'].to_numpy(np.int32)
    assert np.array_equal(cells[pre], edge['Presynaptic_ID'].to_numpy())
    assert np.array_equal(cells[post], edge['Postsynaptic_ID'].to_numpy())
    signed = edge['Excitatory x Connectivity'].to_numpy(np.float32)
    graph = csr_matrix((signed, (post, pre)), shape=(len(cells), len(cells)))
    graph.sum_duplicates()
    graph.eliminate_zeros()
    graph.sort_indices()
    abs_strength = np.asarray(abs(graph).sum(axis=1)).ravel()
    # Preserve direction, sign and relative weights within each receiving neuron.
    # Incoming normalization is an engineered stability choice, not physiology.
    graph.data /= np.repeat(np.maximum(abs_strength, 1), np.diff(graph.indptr))
    annotation = json.loads((DATA / 'circuit_annotations.json').read_text())
    lookup = {int(v): i for i, v in enumerate(cells)}
    sensory = [n for n in annotation['neurons'] if n['role'] in ('lc4', 'lplc2') and int(n['id']) in lookup]
    inputs = np.array([lookup[int(n['id'])] for n in sensory], dtype=np.int32)
    # Read from actual immediate postsynaptic cells; never from directly driven cells.
    transfer = graph[:, inputs].toarray()
    transfer[inputs] = 0
    influence = np.abs(transfer).sum(axis=1)
    candidates = np.flatnonzero(influence > 0)
    # Spread observations across different input channels, avoiding a single dominant group.
    selected = []
    for k in range(len(inputs)):
        ranking = np.argsort(np.abs(transfer[:, k]))[::-1][:8]
        for i in ranking:
            if influence[i] > 0 and int(i) not in selected:
                selected.append(int(i))
                break
        if len(selected) >= 192:
            break
    for i in candidates[np.argsort(influence[candidates])[::-1]]:
        if int(i) not in selected:
            selected.append(int(i))
        if len(selected) >= 192:
            break
    outputs = np.array(selected, dtype=np.int32)
    np.savez_compressed(DATA / 'flywire_graph.npz', data=graph.data, indices=graph.indices,
                        indptr=graph.indptr, neuron_ids=cells, input_indices=inputs,
                        readout_indices=outputs)
    manifest = {
        'dataset': 'FlyWire FAFB v783, Shiu repository prepared subset',
        'neurons': len(cells), 'source_edge_rows': len(edge), 'effective_edges': graph.nnz,
        'source_contact_sum': int(edge['Connectivity'].sum()),
        'input_neurons': len(inputs), 'observed_neurons': len(outputs),
        'input_types': ['LC4', 'LPLC2'], 'readout_directly_driven': False,
        'model': 'signed connectome-constrained leaky tanh rate network; dimensionless activity',
        'normalization': 'signed synaptic counts divided by total absolute incoming weight per neuron',
        'scientific_scope': 'task-transfer prototype; not original LIF physiology, fly vision, or biological learning',
        'upstream_commit': '91bdd1e7dcf193f3e7ca5a8933497fcef63b7960',
        'annotation_commit': '32b00011e83c3dc85fa3ea0b3934155b04f1635d',
        'sources': ['https://github.com/philshiu/Drosophila_brain_model',
                    'https://github.com/DenisSergeevitch/desktop-fly',
                    'https://www.nature.com/articles/s41586-024-07763-9',
                    'https://www.nature.com/articles/s41586-024-07558-y'],
        'data_license': 'CC BY-NC 4.0; see THIRD_PARTY.md',
        'files': {name: {'bytes': (DATA/name).stat().st_size, 'sha256': sha256(DATA/name)}
                  for name in ['Completeness_783.csv', 'Connectivity_783.parquet', 'circuit_annotations.json', 'flywire_graph.npz']},
    }
    (DATA / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf8')
    print(json.dumps({k: manifest[k] for k in ['neurons','source_edge_rows','effective_edges','input_neurons','observed_neurons']}, indent=2))


if __name__ == '__main__':
    prepare()
