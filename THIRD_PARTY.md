# Data attribution and boundaries

## Soma coordinates and updated annotations (anatomy viewer)

- Source: https://github.com/flyconnectome/flywire_annotations
- Pinned commit: `8587524c1748ce5ef2080822a2fc890fc03bf597`; `supplemental_files/Supplemental_file1_neuron_annotations.tsv` saved as `data/neuron_annotations.tsv`.
- Source SHA-256: `9a4f8b2f843196074431ebd7cd883536afa1be86c8a4ce90970441e8be81d1be`.
- Soma coordinates are converted from 4 x 4 x 40 nm voxels to micrometres. Source documentation: https://fafbseg-py.readthedocs.io/en/latest/source/generated/fafbseg.flywire.search_annotations.html . Missing somas are omitted, never replaced by invented coordinates.
- The current annotation release requests citation of Schlegel et al. (2024), Dorkenwald et al. (2024), Matsliah et al., *Neuronal parts list and wiring diagram for a visual system*, Nature (2024), https://doi.org/10.1038/s41586-024-07981-1, and Berg et al., *Sexual dimorphism in the complete connectome of the Drosophila male central nervous system*, bioRxiv (2025), https://doi.org/10.1101/2025.10.09.680999 . These updated female FlyWire annotations incorporate cross-validation; this project does not download or simulate the MaleCNS graph.
- The viewer samples measured somas and overlays this project's dimensionless simulated state magnitude. It does not reconstruct neurites, assign neuropil activation or display measured neuronal activity. Full provenance and coverage: `data/anatomy_manifest.json`.

This project uses measured FlyWire FAFB v783 connectivity, through the original Shiu et al. model repository. It does not include biological organoid recordings.

## Connectivity and neuron list

- Source: https://github.com/philshiu/Drosophila_brain_model
- Commit: `91bdd1e7dcf193f3e7ca5a8933497fcef63b7960`
- Files: `Connectivity_783.parquet`, `Completeness_783.csv`.
- Scientific paper: Shiu et al., *A Drosophila computational brain model reveals sensorimotor processing*, Nature (2024), https://doi.org/10.1038/s41586-024-07763-9.
- The upstream Python implementation is MIT licensed; this project implements its own rate dynamics, not the original Brian2 LIF dynamics. Dataset terms are separate from source-code terms.

## Cell identities used to identify sensory inputs

- Source: https://github.com/DenisSergeevitch/desktop-fly
- Commit: `32b00011e83c3dc85fa3ea0b3934155b04f1635d`
- Upstream `data/circuit.json` is stored here as `data/circuit_annotations.json`; only its real cell IDs / annotations are used to identify LC4 and LPLC2 in the larger network.
- The simulation graph comes from the full prepared Shiu v783 files, not the 668-cell DesktopFly circuit.
- Upstream data terms: `data/DATA_LICENSE.md`. The original license file includes MaleCNS notes; no MaleCNS dataset is included here.

## FlyWire attribution and reuse

These FlyWire derivatives are retained for non-commercial research/education under CC BY-NC 4.0: https://creativecommons.org/licenses/by-nc/4.0/ . Retain attribution and source terms when sharing. The source-code MIT licenses do not supersede dataset terms.

- Dorkenwald et al., *Neuronal wiring diagram of an adult brain*, Nature 634, 124–138 (2024). https://doi.org/10.1038/s41586-024-07558-y
- Schlegel et al., *Whole-brain annotation and multi-connectome cell typing of Drosophila*, Nature 634, 139–152 (2024). https://doi.org/10.1038/s41586-024-07686-5
- FlyWire project: https://flywire.ai/

Source SHA-256 hashes and transformations are recorded in `data/manifest.json`. The prepared upstream neuron list contains 138,639 neurons; this project does not invent missing neurons to match the 139,255 headline number.

## Task inspiration

Kagan et al., *In vitro neurons learn and exhibit sentience when embodied in a simulated game-world*, Neuron 110, 3952–3969.e8 (2022). https://doi.org/10.1016/j.neuron.2022.09.001

DishBrain used neural cultures on HD-MEAs. Its simplified Pong task motivates the environment here. This project does not reproduce its wet-lab system, stimulation protocol, plasticity mechanism or learning claim. The external decoder is trained with explicit demonstration labels and then frozen; the recurrent biological wiring is never trained.
