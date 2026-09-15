"""Small causal checks for the scientific boundary, plus deterministic game mechanics."""
import json
import numpy as np
from fly_model import FlyNetwork,Readout,ROOT
from pong import Pong


def main():
    brain=FlyNetwork()
    readout=Readout.load(ROOT/'results/pong_readout.npz')
    checks={}
    checks['full_prepared_neuron_set']=brain.n==138639
    checks['all_source_edges_retained']=brain.manifest['source_edge_rows']==brain.manifest['effective_edges']==15091983
    checks['no_direct_input_readout_overlap']=np.intersect1d(brain.input_indices,brain.readout_indices).size==0
    a=np.array([-.6,.2,0,-.7,.1],dtype=np.float32)
    brain.reset()
    fa=brain.advance(a)
    brain.reset()
    fb=brain.advance(a)
    checks['reset_replay_matches']=bool(np.allclose(fa,fb,rtol=1e-5,atol=1e-7))
    brain.reset()
    for _ in range(5):fa=brain.advance(a)
    brain.reset()
    b=a.copy();b[0]=.6
    for _ in range(5):fb=brain.advance(b)
    checks['different_sensory_inputs_change_downstream_states']=bool(np.max(np.abs(fa-fb))>1e-3)
    checks['different_sensory_inputs_change_decoded_action']=abs(readout.predict(fa)-readout.predict(fb))>.5
    brain.reset()
    for _ in range(5):zero=brain.advance(a,disconnected=True)
    checks['disconnected_outputs_are_zero']=bool(np.max(np.abs(zero))==0)
    brain.reset()
    for _ in range(5):zero=brain.advance(a,silence_input=True)
    checks['silenced_rest_stays_zero']=bool(np.max(np.abs(zero))==0)
    p1,p2=Pong(987),Pong(987)
    for k in range(300):
        p1.step(np.sin(k));p2.step(np.sin(k))
    checks['same_game_seed_same_actions_same_result']=p1.snapshot()==p2.snapshot()
    report={'checks':checks,'passed':all(checks.values()),'device':brain.device}
    (ROOT/'results/verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':main()
