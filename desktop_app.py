"""Self-contained Windows launcher. No Python install, account or host PC needed."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser

VERSION='1.0.0'
DEFAULT_PORT=8751


def request(port,path,body=None):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,
        None if body is None else json.dumps(body).encode(),{'Content-Type':'application/json'})
    with opener.open(req,timeout=2) as response:return json.load(response)


def running(port):
    try:
        state=request(port,'/api/health')
        return state.get('app')=='flywire-pong-lab' and bool(state.get('desktop_package'))
    except Exception:return False


def self_test(path):
    import numpy as np
    from fly_model import FlyNetwork,Readout,ROOT
    from pong import Pong
    reference=np.load(ROOT/'results/cpu_backend_reference.npz')
    obs=np.array([.5,-.2,.6,-1.1,.4],dtype=np.float32)
    checks={}; timings={}
    for graph,filename in [('real','pong_readout.npz'),('rewired','rewired_readout.npz')]:
        brain=FlyNetwork('cpu',graph=graph)
        for _ in range(6):features=brain.advance(obs)
        checks[graph+'_reference']=bool(np.allclose(features,reference[graph],atol=2e-6,rtol=2e-5))
        action=Readout.load(ROOT/'results'/filename).predict(features)
        checks[graph+'_action']=bool(np.isfinite(action) and -1<=action<=1)
        values=[]
        for _ in range(25):brain.advance(obs);values.append(brain.last_ms)
        timings[graph]={'median_ms':float(np.median(values)),'p95_ms':float(np.percentile(values,95))}
        del brain
    from anatomy import load_anatomy
    display,_,_,meta=load_anatomy()
    geometry=json.loads((ROOT/'web/brain-data.json').read_text(encoding='utf8'))
    checks['anatomy_alignment']=len(display)==len(geometry['points'])==12583
    for filename in ('index.html','app.js','motion.js','brain.html','brain.js','style.css','brain.css'):
        checks[filename]=(ROOT/'web'/filename).stat().st_size>0
    report={'version':VERSION,'frozen':bool(getattr(sys,'frozen',False)),
            'python':sys.version,'device':'cpu','neurons':138639,'edges':15091983,
            'checks':checks,'timings':timings,'passed':all(checks.values())}
    Path(path).write_text(json.dumps(report,indent=2),encoding='utf8')
    if not report['passed']:raise RuntimeError('Packaged self-test failed')


def main():
    parser=argparse.ArgumentParser(description='FlyWire Pong offline desktop app')
    parser.add_argument('--port',type=int,default=DEFAULT_PORT)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--shutdown',action='store_true')
    parser.add_argument('--self-test',metavar='REPORT_JSON')
    parser.add_argument('--ready-file',metavar='READY_JSON')
    args=parser.parse_args()
    if not 1024<=args.port<=65535:raise ValueError('invalid port')
    # Set before NumPy/SciPy imports. Do not oversubscribe a friend's CPU.
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[key]='1'
    if args.self_test:return self_test(args.self_test)
    if args.shutdown:
        if running(args.port):request(args.port,'/api/shutdown',{})
        return
    url=f'http://127.0.0.1:{args.port}/'
    if running(args.port):
        if not args.no_browser:webbrowser.open(url)
        return
    mutex=None
    if sys.platform=='win32':
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateMutexW.restype=ctypes.c_void_p
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p]
        mutex=kernel.CreateMutexW(None,False,f'Local\\FlyWirePongDesktop-{args.port}')
        if ctypes.get_last_error()==183:
            for _ in range(100):
                if running(args.port):
                    if not args.no_browser:webbrowser.open(url)
                    return
                time.sleep(.2)
            raise RuntimeError('游戏正在启动，请稍后再试。')
    def ready(server,lab,config):
        if args.ready_file:
            Path(args.ready_file).write_text(json.dumps({'ready':True,'version':VERSION,'url':url,'pid':os.getpid()}),encoding='utf8')
        if not args.no_browser:webbrowser.open(url)
        def idle_exit():
            while not lab.stop.wait(15):
                if time.perf_counter()-lab.last_contact>600:
                    lab.stop.set();server.shutdown();return
        threading.Thread(target=idle_exit,daemon=True).start()
    try:
        from server import main as run_server
        run_server(['--port',str(args.port),'--device','cpu'],on_ready=ready,desktop_version=VERSION)
    finally:
        if mutex:
            kernel.CloseHandle.argtypes=[ctypes.c_void_p]
            kernel.CloseHandle(mutex)


if __name__=='__main__':
    log_dir=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'FlyWirePong'/'logs'
    log_dir.mkdir(parents=True,exist_ok=True)
    log=(log_dir/'desktop.log').open('a',encoding='utf8',buffering=1)
    sys.stdout=sys.stderr=log
    try:main()
    except Exception:
        traceback.print_exc()
        if '--self-test' not in sys.argv and '--no-browser' not in sys.argv and '--shutdown' not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None,f'启动失败，请将此日志交给分享者排查：\n{log_dir / "desktop.log"}', 'FlyWire Pong',0x10)
        sys.exit(1)
