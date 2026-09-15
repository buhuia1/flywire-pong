"""Apply the same downstream-cell selection rule to every graph comparison."""
import numpy as np


def select_readouts(graph, inputs, count=192):
    transfer = graph[:, inputs].toarray()
    transfer[inputs] = 0
    influence = np.abs(transfer).sum(axis=1)
    candidates = np.flatnonzero(influence > 0)
    selected = []
    for k in range(len(inputs)):
        ranking = np.argsort(np.abs(transfer[:, k]))[::-1][:8]
        for i in ranking:
            if influence[i] > 0 and int(i) not in selected:
                selected.append(int(i))
                break
        if len(selected) >= count:
            break
    for i in candidates[np.argsort(influence[candidates])[::-1]]:
        if int(i) not in selected:
            selected.append(int(i))
        if len(selected) >= count:
            break
    if len(selected) != count:
        raise ValueError('Insufficient downstream readout cells')
    return np.array(selected, dtype=np.int32)
