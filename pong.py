"""Single-paddle assay and human-right / neural-left Pong. No learning inside physics."""
import math
import numpy as np

DT = .05
PADDLE_X = .055
RIGHT_X = .945
BALL_RADIUS = .012
DIFFICULTIES = {
    'easy': {'label': '入门', 'speed': .46, 'paddle_half': .115},
    'normal': {'label': '进阶', 'speed': .75, 'paddle_half': .078},
    'hard': {'label': '挑战', 'speed': 1.10, 'paddle_half': .048},
}


class Pong:
    def __init__(self, seed=1001, difficulty='normal', opponent='wall'):
        if difficulty not in DIFFICULTIES or opponent not in ('human', 'wall'):
            raise ValueError('unknown game configuration')
        self.seed, self.difficulty, self.opponent = seed, difficulty, opponent
        self.rng = np.random.default_rng(seed)
        config = DIFFICULTIES[difficulty]
        self.speed, self.paddle_half = config['speed'], config['paddle_half']
        self.right_half = .105
        self.time = 0.0
        self.hits = self.misses = self.rally = self.best = 0
        self.right_hits = self.right_misses = 0
        self.last_event = 'ready'
        self.paddle = self.right_paddle = self.right_target = .5
        self.aim = -20.0
        self.waiting_serve = False
        self.launch()

    def launch(self):
        if self.opponent == 'human':
            self.waiting_serve = True
            self.x, self.y = RIGHT_X - BALL_RADIUS - .001, self.right_paddle
            self.vx = self.vy = 0.0
        else:
            self.waiting_serve = False
            self.x = .85
            self.y = float(self.rng.uniform(.12, .88))
            angle = float(self.rng.uniform(-.60, .60))
            self.vx = -self.speed * math.cos(angle)
            self.vy = self.speed * math.sin(angle)

    def serve(self):
        if self.opponent == 'human' and self.waiting_serve:
            self.waiting_serve = False
            self.x, self.y = RIGHT_X - BALL_RADIUS - .002, self.right_paddle
            self.aimed_return()
            self.last_event = 'serve'
            return True
        return False

    def aimed_return(self):
        angle = math.radians(self.aim)
        self.vx = -self.speed * math.cos(angle)
        self.vy = self.speed * math.sin(angle)

    def set_player(self, y=None, aim=None):
        if y is not None:
            self.right_target = float(np.clip(y, self.right_half, 1 - self.right_half))
            # Human mouse/touch input is a position, not a slow movement command.
            self.right_paddle = self.right_target
            if self.waiting_serve:
                self.y = self.right_paddle
        if aim is not None:
            self.aim = float(np.clip(aim, -55, 55))

    def observation(self):
        return np.array([2*self.y-1, 2*self.paddle-1, 2*self.x-1,
                         self.vx/.6, self.vy/.6], dtype=np.float32)

    def teacher(self):
        return float(np.clip((self.y-self.paddle)*9, -1, 1))

    def step(self, action):
        action = float(np.clip(action, -1, 1))
        self.paddle = float(np.clip(self.paddle + action*.72*DT, self.paddle_half, 1-self.paddle_half))
        self.right_paddle += float(np.clip(self.right_target-self.right_paddle, -1.5*DT, 1.5*DT))
        if self.waiting_serve:
            self.x, self.y = RIGHT_X-BALL_RADIUS-.001, self.right_paddle
            return None
        self.x += self.vx*DT
        self.y += self.vy*DT
        if self.y < BALL_RADIUS:
            self.y = 2*BALL_RADIUS-self.y
            self.vy = abs(self.vy)
        elif self.y > 1-BALL_RADIUS:
            self.y = 2*(1-BALL_RADIUS)-self.y
            self.vy = -abs(self.vy)
        event = None
        if self.vx > 0:
            right_limit = RIGHT_X-BALL_RADIUS if self.opponent == 'human' else 1-BALL_RADIUS
            if self.x >= right_limit:
                if self.opponent == 'wall':
                    self.x = 2*right_limit-self.x
                    self.vx = -abs(self.vx)
                elif abs(self.y-self.right_paddle) <= self.right_half+BALL_RADIUS:
                    self.x = 2*right_limit-self.x
                    self.aimed_return()
                    self.right_hits += 1
                    event = 'human_hit'
                else:
                    self.right_misses += 1
                    self.rally = 0
                    self.launch()
                    event = 'human_miss'
        if self.vx < 0 and self.x <= PADDLE_X+BALL_RADIUS:
            if abs(self.y-self.paddle) <= self.paddle_half+BALL_RADIUS:
                self.x = 2*(PADDLE_X+BALL_RADIUS)-self.x
                offset = (self.y-self.paddle)/self.paddle_half
                angle = float(np.clip(offset*.82 + math.atan2(self.vy, abs(self.vx))*.2, -1.02, 1.02))
                # Prevent gradually flattening trajectories from making play trivial.
                if abs(angle) < .16:
                    angle = math.copysign(.16, self.vy or offset or 1)
                self.vx = self.speed*math.cos(angle)
                self.vy = self.speed*math.sin(angle)
                self.hits += 1
                self.rally += 1
                self.best = max(self.best, self.rally)
                event = 'hit'
            else:
                self.misses += 1
                self.rally = 0
                self.launch()
                event = 'miss'
        self.time += DT
        if event:
            self.last_event = event
        return event

    def snapshot(self):
        total = self.hits+self.misses
        return {'seed': self.seed, 'time': self.time, 'ball': {'x': self.x, 'y': self.y, 'vx': self.vx, 'vy': self.vy},
                'paddle': self.paddle, 'paddle_half': self.paddle_half, 'hits': self.hits, 'misses': self.misses,
                'best': self.best, 'rally': self.rally, 'hit_rate': self.hits/total if total else None,
                'event': self.last_event, 'difficulty': self.difficulty, 'opponent': self.opponent,
                'right_paddle': self.right_paddle, 'right_target': self.right_target, 'right_half': self.right_half,
                'right_hits': self.right_hits, 'right_misses': self.right_misses, 'aim': self.aim,
                'waiting_serve': self.waiting_serve, 'ball_speed': self.speed}
