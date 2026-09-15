"""Join published soma coordinates to model IDs; never invent missing positions."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
COMMIT = '8587524c1748ce5ef2080822a2fc890fc03bf597'
SOURCE = f'https://raw.githubusercontent.com/flyconnectome/flywire_annotations/{COMMIT}/supplemental_files/Supplemental_file1_neuron_annotations.tsv'


def main():
    raw = ROOT/'data/neuron_annotations.tsv'
    table = pd.read_csv(raw, sep='\t', dtype={'root_id': str}, low_memory=False)
    assert not table.root_id.duplicated().any()
    real = np.load(ROOT/'data/flywire_graph.npz', allow_pickle=False)
    rewired = np.load(ROOT/'data/rewired_graph.npz', allow_pickle=False)
    ids = real['neuron_ids'].astype(str)
    rows = table.set_index('root_id').reindex(ids)
    xyz = rows[['soma_x', 'soma_y', 'soma_z']].to_numpy(float)
    valid = np.flatnonzero(np.isfinite(xyz).all(axis=1))
    # Coordinates in the official annotations are 4 x 4 x 40 nm voxels.
    xyz *= np.array([.004, .004, .04])
    rng = np.random.default_rng(20260915)
    base = rng.choice(valid, min(12000, len(valid)), replace=False)
    mandatory = np.concatenate((real['input_indices'], real['readout_indices'], rewired['readout_indices']))
    display = np.union1d(base, np.intersect1d(mandatory, valid)).astype(np.int32)
    classes = rows.super_class.fillna('unknown')
    class_names = sorted(classes.unique())
    class_codes = np.array([class_names.index(x) for x in classes], np.int16)
    types = rows.cell_type.fillna('untyped').astype(str)
    type_codes, type_names = pd.factorize(types, sort=True)
    role = np.zeros(len(ids), np.uint8)
    role[real['input_indices']] |= 1
    role[real['readout_indices']] |= 2
    role[rewired['readout_indices']] |= 4
    np.savez_compressed(ROOT/'data/anatomy_indices.npz', display=display,
                        class_codes=class_codes, type_codes=type_codes)
    manifest = {
        'source': SOURCE, 'commit': COMMIT, 'sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
        'source_rows': len(table), 'model_neurons': len(ids),
        'matched_annotations': int(rows.supervoxel_id.notna().sum()),
        'neurons_with_soma': len(valid), 'displayed_somas': len(display),
        'missing_soma_not_plotted': len(ids)-len(valid), 'sampling_seed': 20260915,
        'input_somas': int(np.isin(real['input_indices'], valid).sum()),
        'real_readout_somas': int(np.isin(real['readout_indices'], valid).sum()),
        'rewired_readout_somas': int(np.isin(rewired['readout_indices'], valid).sum()),
        'coordinate_units': 'micrometres; source soma voxels multiplied by [0.004,0.004,0.04]',
        'coordinate_reference': 'https://fafbseg-py.readthedocs.io/en/latest/source/generated/fafbseg.flywire.search_annotations.html',
        'scope': 'Measured soma locations, sampled for display. No neurite morphology, neuropil assignment, or measured activity.',
        'type_names': type_names.tolist(), 'class_names': class_names,
    }
    (ROOT/'data/anatomy_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    geometry = {
        'manifest': {k:v for k,v in manifest.items() if k!='type_names'},
        'class_names': class_names,
        'points': [[str(ids[i]), *np.round(xyz[i], 2).tolist(), int(class_codes[i]), str(types.iloc[i]), int(role[i])]
                   for i in display],
    }
    (ROOT/'web/brain-data.json').write_text(json.dumps(geometry, ensure_ascii=False, separators=(',',':')), encoding='utf8')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ('type_names','class_names')}, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
