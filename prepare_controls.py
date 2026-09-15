"""Signed source-shuffle control. Deliberately artificial wiring, never biological data."""
from pathlib import Path
import hashlib
import json
import time
import numpy as np
from scipy.sparse import csr_matrix
from graph_utils import select_readouts

ROOT = Path(__file__).resolve().parent


def main():
    started = time.perf_counter()
    source = ROOT/'data/flywire_graph.npz'
    z = np.load(source, allow_pickle=False)
    n = len(z['neuron_ids'])
    data, indptr, original = z['data'], z['indptr'], z['indices']
    indices = original.copy()
    rng = np.random.default_rng(20260915)
    for sign in (1, -1):
        positions = np.flatnonzero(data * sign > 0)
        indices[positions] = rng.permutation(original[positions])
    graph = csr_matrix((data, indices, indptr), shape=(n, n))
    real = csr_matrix((data, original, indptr), shape=(n, n))
    # Validate that the shared selector reproduces the original real-graph ports.
    assert np.array_equal(select_readouts(real, z['input_indices']), z['readout_indices'])
    readouts = select_readouts(graph, z['input_indices'])
    checks = {
        'same_edge_entries': len(indices) == len(original),
        'same_receiving_slots_and_weights': np.array_equal(graph.indptr, indptr) and np.array_equal(graph.data, data),
        'same_outgoing_edge_entry_counts': np.array_equal(np.bincount(indices, minlength=n), np.bincount(original, minlength=n)),
        'input_readout_disjoint': not bool(np.intersect1d(z['input_indices'], readouts).size),
        'changed_source_fraction': float(np.mean(indices != original)),
    }
    assert all(value for key, value in checks.items() if key != 'changed_source_fraction')
    assert checks['changed_source_fraction'] > .99
    counted = graph.copy()
    counted.sum_duplicates()
    output = ROOT/'data/rewired_graph.npz'
    np.savez_compressed(output, data=data, indices=indices, indptr=indptr,
                        neuron_ids=z['neuron_ids'], input_indices=z['input_indices'], readout_indices=readouts)
    report = {
        'kind': 'artificial signed presynaptic-source shuffle', 'seed': 20260915,
        'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'file_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'neurons': n, 'edge_entries': len(indices), 'distinct_pairs': counted.nnz,
        'parallel_entries_after_shuffle': len(indices) - counted.nnz,
        'matched': ['signed source multiplicities', 'receiving edge slots', 'each receiving signed weight',
                    'node count', 'encoder', 'number of readouts', 'readout-selection procedure', 'training budget'],
        'not_matched': ['outgoing strength per neuron', 'unique-neighbor degree', 'individual readout cell IDs'],
        'caveat': 'One artificial graph seed; permits parallel edges/autapses. Not a full degree/strength-preserving ensemble.',
        'checks': checks, 'seconds': time.perf_counter() - started,
    }
    (ROOT/'data/rewired_manifest.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
