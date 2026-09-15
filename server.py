from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from collections import deque
import threading
import argparse
import json
import mimetypes
import time
import numpy as np
from fly_model import FlyNetwork,Readout,ROOT
from pong import Pong,DT,DIFFICULTIES
from anatomy import snapshot as anatomy_snapshot

MODES = ('fly','rewired','direct','untrained','disconnected','silenced','random','rule','manual')


def validate_command(command):
    allowed = {'mode','paused','reset','seed','manual','opponent','difficulty','player_y','aim','serve'}
    if not isinstance(command,dict) or set(command)-allowed:
        raise ValueError('unknown command')
    if 'mode' in command and command['mode'] not in MODES:
        raise ValueError('unknown mode')
    if 'difficulty' in command and command['difficulty'] not in DIFFICULTIES:
        raise ValueError('unknown difficulty')
    if 'opponent' in command and command['opponent'] not in ('human','wall'):
        raise ValueError('unknown opponent')
    for key in ('paused','reset','serve'):
        if key in command and type(command[key]) is not bool:
            raise ValueError('boolean required')
    if 'seed' in command and (type(command['seed']) is not int or not 0<=command['seed']<=2147483647):
        raise ValueError('invalid seed')
    for key,low,high in [('manual',-1,1),('player_y',0,1),('aim',-55,55)]:
        if key in command and (not isinstance(command[key],(int,float)) or not np.isfinite(command[key]) or not low<=command[key]<=high):
            raise ValueError('invalid '+key)


def make_metadata(brains):
    real = brains['real']
    return {'manifest':real.manifest,'config':real.config(),'version':2,
            'difficulties':DIFFICULTIES,
            'readout_ids':[str(real.ids[i]) for i in real.readout_indices],
            'readout_ids_by_graph':{name:[str(b.ids[i]) for i in b.readout_indices] for name,b in brains.items()},
            'rewired':json.loads((ROOT/'data/rewired_manifest.json').read_text()),
            'training':json.loads((ROOT/'results/training.json').read_text()),
            'benchmark':json.loads((ROOT/'results/benchmark.json').read_text())}


class Lab:
    def __init__(self,device,brain=None,brains=None):
        self.brains=brains or {'real':brain if brain is not None else FlyNetwork(device),
                              'rewired':FlyNetwork(device,graph='rewired')}
        self.brain=self.brains['real']
        self.decoders={name:Readout.load(ROOT/'results'/file) for name,file in
                       [('real','pong_readout.npz'),('rewired','rewired_readout.npz'),('direct','direct_readout.npz')]}
        self.decoder=self.decoders['real']
        self.untrained=Readout(np.random.default_rng(777).normal(0,.3,len(self.brain.readout_indices)+1))
        self.lock=threading.RLock()
        self.stop=threading.Event()
        self.seed=1001
        self.difficulty='normal'
        self.opponent='human'
        self.game=Pong(self.seed,self.difficulty,self.opponent)
        self.mode='fly'
        self.paused=False
        self.action=0.
        self.manual=0.
        self.rng=np.random.default_rng(8888)
        self.features=np.zeros(len(self.brain.readout_indices))
        self.events=deque(maxlen=7)
        self.records=deque(maxlen=10000)
        self.actual_hz=0
        self.steps=0
        self.state_clock=time.perf_counter()
        self.last_contact=time.perf_counter()
        self.auto_suspend=False
        self.started=time.perf_counter()
        self.thread=threading.Thread(target=self.loop,daemon=True)
        self.thread.start()

    def reset(self,seed=None):
        self.seed=int(seed) if seed is not None else self.seed+1
        self.game=Pong(self.seed,self.difficulty,self.opponent)
        for brain in self.brains.values():brain.reset()
        self.action=self.manual=0.
        self.brain.last_ms=0.
        self.features*=0
        self.events.clear()
        self.records.clear()
        self.rng=np.random.default_rng(self.seed+8888)
        self.steps=0
        self.started=time.perf_counter()

    def control(self,command):
        validate_command(command)
        with self.lock:
            changed=any(key in command for key in ('mode','difficulty','opponent'))
            for key in ('mode','difficulty','opponent'):
                if key in command:setattr(self,key,command[key])
            self.brain=self.brains['rewired' if self.mode=='rewired' else 'real']
            if changed or command.get('reset'):
                self.reset(command.get('seed',self.seed+int(bool(command.get('reset')))))
            if 'paused' in command:self.paused=command['paused']
            if 'manual' in command:self.manual=float(command['manual'])
            self.game.set_player(command.get('player_y'),command.get('aim'))
            if command.get('serve'):
                if self.game.serve():
                    for brain in self.brains.values():brain.reset()
                    self.events.appendleft({'event':'serve','time':round(self.game.time,1)})
                self.paused=False
        return self.snapshot()

    def input(self,command):
        validate_command(command)
        if not command or set(command)-{'player_y','aim'}:
            raise ValueError('player input only')
        with self.lock:
            self.game.set_player(command.get('player_y'),command.get('aim'))
        return {'ok':True}

    def loop(self):
        interval_start=time.perf_counter();interval_steps=0
        deadline=time.perf_counter()
        while not self.stop.is_set():
            begin=time.perf_counter()
            with self.lock:
                if not self.paused and not (self.auto_suspend and time.perf_counter()-self.last_contact>15):
                    obs=self.game.observation()
                    waiting=self.game.waiting_serve
                    neural=self.mode in ('fly','rewired','untrained','disconnected','silenced')
                    if waiting:
                        self.action=0.
                        self.brain.reset()
                        self.features*=0
                        self.brain.last_ms=0.
                    elif neural:
                        self.features=self.brain.advance(obs,disconnected=self.mode=='disconnected',silence_input=self.mode=='silenced')
                        self.action=(self.untrained if self.mode=='untrained' else self.decoders['rewired' if self.mode=='rewired' else 'real']).predict(self.features)
                    elif self.mode=='direct':
                        self.action=self.decoders['direct'].predict(obs)
                        self.features*=0
                    elif self.mode=='manual':
                        self.action=self.manual
                        self.features*=0
                    elif self.mode=='rule':
                        self.action=self.game.teacher()
                        self.features*=0
                    else:
                        self.action=float(self.rng.choice([-1,0,1]))
                        self.features*=0
                    event=self.game.step(self.action)
                    self.state_clock=time.perf_counter()
                    interval_steps+=1
                    if not waiting:
                        self.steps+=1
                        self.records.append({'step':self.steps,'seed':self.seed,'mode':self.mode,
                            'difficulty':self.difficulty,'opponent':self.opponent,
                            'observation':obs.tolist(),'action':self.action,'event':event,
                            'player_y':self.game.right_paddle,'aim':self.game.aim,
                            'hits':self.game.hits,'misses':self.game.misses,
                            'right_hits':self.game.right_hits,'right_misses':self.game.right_misses})
                    if event:
                        self.events.appendleft({'event':event,'time':round(self.game.time,1)})
            now=time.perf_counter()
            if now-interval_start>=1:
                self.actual_hz=interval_steps/(now-interval_start)
                interval_steps=0;interval_start=now
            deadline+=DT
            now=time.perf_counter()
            if deadline<now-DT:deadline=now
            self.stop.wait(max(0,deadline-now))

    def snapshot(self):
        with self.lock:
            return {'app':'flywire-pong-lab','version':2,'game':self.game.snapshot(),'mode':self.mode,
                'paused':self.paused,'action':self.action,'features':self.features.tolist(),
                'server_age_ms':max(0,(time.perf_counter()-self.state_clock)*1000),
                'observation':self.game.observation().tolist(),'neural_ms':self.brain.last_ms,
                'actual_hz':self.actual_hz,'network_steps':self.brain.ticks,'events':list(self.events),
                'recorded_steps':len(self.records),'graph':self.brain.graph,'online_learning':False}


def main(argv=None, on_ready=None, desktop_version=None):
    ap=argparse.ArgumentParser()
    ap.add_argument('--port',type=int,default=8741)
    ap.add_argument('--device',default='auto',choices=['auto','cpu','cuda'])
    args=ap.parse_args(argv)
    lab=Lab(args.device)
    lab.auto_suspend=bool(desktop_version)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def send_json(self,value,status=200):
            content=json.dumps(value,ensure_ascii=False,allow_nan=False).encode('utf8')
            self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(content)))
            self.end_headers();self.wfile.write(content)
        def do_GET(self):
            route=self.path.split('?')[0]
            if route in ('/api/state','/api/brain','/api/meta'):
                lab.last_contact=time.perf_counter()
            if route=='/api/health':
                return self.send_json({'app':'flywire-pong-lab','desktop_package':desktop_version,'ready':True})
            if route=='/api/state':return self.send_json(lab.snapshot())
            if route=='/api/brain':return self.send_json(anatomy_snapshot(lab))
            if route=='/api/meta':
                return self.send_json(make_metadata(lab.brains))
            if route=='/api/export':
                with lab.lock:
                    rows=list(lab.records)
                return self.send_json({'config':lab.brain.config(),'records':rows,
                    'limit':10000,'scope':'simulated network, last 10000 game decisions; no biological data'})
            routes={'/':'index.html','/app.js':'app.js','/motion.js':'motion.js','/style.css':'style.css',
                    '/brain':'brain.html','/brain.js':'brain.js','/brain.css':'brain.css','/brain-data.json':'brain-data.json'}
            if route not in routes:return self.send_json({'error':'not found'},404)
            file=ROOT/'web'/routes[route]
            payload=file.read_bytes()
            if desktop_version and route=='/':
                page=payload.decode('utf8').replace('停止本地服务','退出游戏')
                page=page.replace('真实连接组 · 人机对打与对照实验','Windows 离线版 · 本机 CPU 计算')
                page=page.replace('<footer>', '<p class="caption">独立安装版：切到后台 15 秒后暂停计算，返回自动恢复；关闭所有游戏页面 10 分钟后自动退出。</p><footer>')
                payload=page.encode('utf8')
            self.send_response(200)
            self.send_header('Content-Type',mimetypes.guess_type(file.name)[0]+'; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers();self.wfile.write(payload)
        def do_POST(self):
            # Local UI only. Reject cross-origin browser requests before reading commands.
            origin=self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{args.port}',f'http://localhost:{args.port}'):
                return self.send_json({'error':'origin rejected'},403)
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length>2048:return self.send_json({'error':'request too large'},413)
                command=json.loads(self.rfile.read(length) or b'{}')
                lab.last_contact=time.perf_counter()
                if self.path=='/api/input':
                    return self.send_json(lab.input(command))
                if self.path=='/api/shutdown':
                    self.send_json({'stopped':True})
                    lab.stop.set()
                    threading.Thread(target=server.shutdown,daemon=True).start()
                    return
                if self.path!='/api/control':return self.send_json({'error':'not found'},404)
                self.send_json(lab.control(command))
            except (ValueError,TypeError,json.JSONDecodeError) as e:
                self.send_json({'error':str(e)},400)

    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    if on_ready:on_ready(server,lab,args)
    print(f'FlyWire Pong ready: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    finally:lab.stop.set();server.server_close()


if __name__=='__main__':main()
