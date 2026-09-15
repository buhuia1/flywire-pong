"""Record actual full-network inference for the static phone-friendly preview."""
from pathlib import Path
import os,sys,json,hashlib
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
from fly_model import FlyNetwork,Readout
from pong import Pong,DT

def main():
 brain=FlyNetwork('cpu');decoder=Readout.load(ROOT/'results/pong_readout.npz')
 display=np.load(ROOT/'data/anatomy_indices.npz')['display']
 game=Pong(1001,'normal','wall');frames=[];activity=[];times=[]
 for step in range(600):
  # Each record contains the state that supplied this neural input, so game and activity align.
  observation=game.observation();features=brain.advance(observation);action=decoder.predict(features)
  frames.append([*[round(float(v),6) for v in (game.x,game.y,game.vx,game.vy,game.paddle)],game.hits,game.misses,round(action,6)])
  if step%5==0:
   values=np.abs(brain.x[display])
   quantized=np.rint(np.clip((np.log10(np.maximum(values,1e-6))+6)/6,0,1)*255).astype(np.uint8)
   activity.append(quantized);times.append(round(step*DT,2))
  game.step(action)
 output=ROOT/'docs/assets';output.mkdir(exist_ok=True)
 raw=np.stack(activity).tobytes();(output/'activity.bin').write_bytes(raw)
 metadata={'version':1,'duration_seconds':30,'dt':DT,'seed':1001,'difficulty':'normal','opponent':'wall','mode':'fly','online_learning':False,'neurons':brain.n,'edges':brain.manifest['effective_edges'],'displayed_somas':len(display),'activity_dt':.25,'activity_frames':len(activity),'activity_encoding':'uint8, row-major [time, displayed soma]; round(255 * clip((log10(max(abs(x),1e-6))+6)/6,0,1)); dimensionless simulated state, not measured activity','activity_sha256':hashlib.sha256(raw).hexdigest(),'graph_sha256':brain.manifest['files']['flywire_graph.npz']['sha256'],'readout_sha256':hashlib.sha256((ROOT/'results/pong_readout.npz').read_bytes()).hexdigest(),'frame_columns':['ball_x','ball_y','ball_vx','ball_vy','left_paddle','hits','misses','action'],'paddle_half':game.paddle_half,'frames':frames}
 (output/'replay.json').write_text(json.dumps(metadata,separators=(',',':')),encoding='utf8')
 print(json.dumps({'frames':len(frames),'activity_frames':len(activity),'activity_bytes':len(raw),'hits':game.hits,'misses':game.misses}))

if __name__=='__main__':main()
