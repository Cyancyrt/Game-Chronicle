"""Seeded dungeon generation and persistent exploration state. No terminal dependencies."""
from dataclasses import dataclass,field
from random import Random
from hashlib import sha256
from .grid import DIRECTIONS,add,neighbors,distance,shortest
from .content import FLOORS
from .gridcombat import GridBattle
from .tactical import TacticalBattle, OBJECTIVES
from .items import ITEMS,grant,use_item

GENERATOR_VERSION=1

def seed_for(*parts):
    return int.from_bytes(sha256(':'.join(map(str,parts)).encode()).digest()[:8],'big')

def key(p): return f'{p[0]},{p[1]}'
def coord(s): return tuple(map(int,s.split(',')))

@dataclass
class FloorMap:
    width:int
    height:int
    tiles:set
    features:dict
    entrance:tuple
    boss:tuple
    encounters:dict
    tier:int
    theme:object


def generate(seed,index,total=10):
    rng=Random(seed_for(GENERATOR_VERSION,seed,index,total,'map'))
    w=19+2*min(4,index//2)+2*rng.randrange(2); h=13+2*min(2,index//3)+2*rng.randrange(2)
    start=(1,1); tiles={start}; stack=[start]
    while stack:
        p=stack[-1]; options=[]
        for dx,dy in DIRECTIONS.values():
            n=(p[0]+2*dx,p[1]+2*dy)
            if 0<n[0]<w-1 and 0<n[1]<h-1 and n not in tiles: options.append((n,(p[0]+dx,p[1]+dy)))
        if options:
            n,m=rng.choice(options); tiles.update((n,m)); stack.append(n)
        else: stack.pop()
    # Open several 3x3 / 5x3 rooms and loops without disconnecting the maze.
    for _ in range(4+index//2):
        x=rng.randrange(1,w-4); y=rng.randrange(1,h-3)
        room_width=rng.choice((3,5))
        tiles.update((a,b) for a in range(x,x+room_width) for b in range(y,y+3) if a<w-1 and b<h-1)
    loops=[(x,y) for x in range(1,w-1) for y in range(1,h-1) if (x,y) not in tiles and sum(n in tiles for n in neighbors((x,y)))>=2]
    rng.shuffle(loops); tiles.update(loops[:6+index])
    # Distance by traversable path, not Euclidean distance.
    from collections import deque
    dist={start:0}; q=deque([start])
    while q:
        p=q.popleft()
        for n in neighbors(p):
            if n in tiles and n not in dist: dist[n]=dist[p]+1; q.append(n)
    far=max(dist.values()); boss=rng.choice(sorted(p for p,d in dist.items() if d>=far-2))
    # A locked boss must not cut off access to a guardian: select from reachable cells with boss blocked.
    reachable={start}; q=deque([start])
    while q:
        for n in neighbors(q.popleft()):
            if n in tiles and n!=boss and n not in reachable: reachable.add(n); q.append(n)
    candidates=sorted(p for p in reachable if dist[p]>=4 and p!=start)
    rng.shuffle(candidates)
    features={start:'entrance',boss:'boss'}; encounters={}
    phase=min(4,index*5//total); theme=FLOORS[phase]; tier=theme.recommended
    if index==total-1: theme=FLOORS[-1]; tier=theme.recommended
    for i in range(3+min(4,index//2)):
        p=candidates.pop(); features[p]='guardian' if i<3 else 'enemy'
        primary=rng.choice(theme.encounters); names=[primary]
        if index>=2 and rng.random()<min(.7,.25+index*.045): names.append(rng.choice(theme.encounters))
        if index>=6 and rng.random()<.18: names.append(rng.choice(theme.encounters))
        encounters[p]=names
    encounters[boss]=[theme.boss]
    for kind,n in [('treasure',3+min(5,index//2)),('cache',2+min(3,index//3)),('trap',2+min(5,index//2)),('camp',1),('altar',1),('shop',1)]:
        for _ in range(n): features[candidates.pop()]=kind
    return FloorMap(w,h,tiles,features,start,boss,encounters,tier,theme)

@dataclass
class Progress:
    seed:int
    total:int=10
    position:str='1,1'
    cleared:list=field(default_factory=list)
    seen:list=field(default_factory=list)
    attempts:dict=field(default_factory=dict)
    events:int=0

class ProceduralDungeon:
    def __init__(self,hero,progress,mode="tactical",rules=None):
        if mode not in ("tactical","grid"): raise ValueError("unknown combat mode")
        self.mode=mode; self.rules=rules
        self.hero=hero; self.progress=progress; self.active_battle=None; self._generate(); self.reveal()
    def _generate(self): self.map=generate(self.progress.seed,self.hero.floor,self.progress.total)
    @property
    def position(self): return coord(self.progress.position)
    @property
    def feature(self): return self.map.features.get(self.position,'floor')
    @property
    def seals(self): return sum(key(p) in self.progress.cleared for p,k in self.map.features.items() if k=='guardian')
    @property
    def pending(self): return self.position in self.map.encounters and self.progress.position not in self.progress.cleared and not self.hero.finished
    def reveal(self):
        known=set(self.progress.seen)
        known.update(key((x,y)) for y in range(self.map.height) for x in range(self.map.width) if distance((x,y),self.position)<=3)
        self.progress.seen=sorted(known)
    def move(self,direction):
        if self.hero.finished or self.pending: return False,'Selesaikan encounter dahulu.'
        if direction not in DIRECTIONS: return False,'Arah tidak valid.'
        p=add(self.position,DIRECTIONS[direction])
        if p not in self.map.tiles: return False,'Terhalang dinding.'
        if p==self.map.boss and self.seals<3: return False,'Gerbang boss terkunci: butuh 3 segel.'
        self.progress.position=key(p); self.reveal()
        if self.feature=='trap' and self.progress.position not in self.progress.cleared:
            self.progress.cleared.append(self.progress.position); damage=min(self.hero.hp-1,3+self.hero.floor//2); self.hero.hp-=damage
            return True,f'Jebakan! -{damage} HP.'
        return True,f'Lokasi: {self.feature}.'
    def encounter(self):
        if not self.pending: raise ValueError('Tidak ada encounter.')
        if self.active_battle is None:
            p=self.progress; n=p.attempts.get(p.position,0)
            rng=Random(seed_for(p.seed,self.hero.floor,p.position,n,'battle'))
            names=list(self.map.encounters[self.position])
            if self.mode=='grid': self.active_battle=GridBattle(self.hero,names,self.map.tier,boss=self.feature=='boss',rng=rng)
            else:
                objective=rng.choice(OBJECTIVES) if self.feature=='enemy' else 'elimination'
                if self.feature=='enemy' and self.hero.floor>=2 and rng.random()<.25: names[-1]='Mirror Mimic'
                self.active_battle=TacticalBattle(self.hero,names,self.map.tier,boss=self.feature=='boss',rng=rng,objective=objective,rules=self.rules)
        return self.active_battle
    def resolve(self,battle):
        if battle is not self.active_battle or battle.result not in ('victory','defeat','fled') or not self.pending: raise ValueError('Encounter tidak valid.')
        self.active_battle=None; h=self.hero; p=self.progress; loc=p.position
        p.attempts[loc]=p.attempts.get(loc,0)+1
        if battle.result=='victory':
            boss=self.feature=='boss'; p.cleared.append(loc); h.wins+=1
            xp=(50 if boss else 26)+self.map.tier*4+10*(getattr(battle,"initial_enemies",len(battle.enemies))-1); gold=(16 if boss else 8)+self.map.tier
            h.gold+=gold; h.recover(); messages=[f'Menang! +{xp} XP, +{gold} gold.',*h.gain_xp(xp)]
            rng=Random(seed_for(p.seed,h.floor,loc,'drop'))
            if boss or rng.random()<.65:
                item=rng.choice(list(ITEMS)); grant(h,item); messages.append(f'Drop: {ITEMS[item].name}.')
            if boss and h.floor==p.total-1: h.finished=True; messages.append('Campaign selesai!')
            elif boss: messages.append('Tekan N di petak boss untuk turun.')
            return messages
        p.position=key(self.map.entrance)
        if battle.result=='defeat':
            h.defeats+=1; lost=min(h.gold,8); h.gold-=lost; h.restore(); return [f'Kalah. Kembali ke entrance, -{lost} gold.']
        return ['Kabur ke entrance. Tidak ada reward.']
    def interact(self,attr='WIS'):
        if self.pending or self.hero.finished: return False,'Selesaikan encounter dahulu.'
        p=self.progress; h=self.hero; kind=self.feature
        if p.position in p.cleared: return False,'Sudah digunakan.'
        rng=Random(seed_for(p.seed,h.floor,p.position,'loot'))
        if kind in ('treasure','cache'):
            rarity=rng.choices(['Common','Rare','Epic','Legendary'],[55,28,14,3])[0] if kind=='treasure' else 'Common'
            rank=['Common','Rare','Epic','Legendary'].index(rarity); gold=rng.randint(5,12)*(rank+1) if kind=='treasure' else 0
            h.gold+=gold; drops=[]
            pool=['potion','ether','ration','antidote'] if rank==0 else list(ITEMS)
            if rank>=2: pool=['greater','shield','bomb','elixir']
            for _ in range(1+rank+(kind=='treasure')):
                item=rng.choice(pool); grant(h,item); drops.append(ITEMS[item].name)
            msg=f'{rarity}: +{gold} gold; '+', '.join(drops)
        elif kind=='camp': h.restore(); msg='Camp: HP, MP, ST pulih penuh.'
        elif kind=='altar':
            if attr not in ('WIS','CHA','INT'): return False,'Atribut tidak valid.'
            value=rng.randint(1,20)+2+h.attrs[attr]
            if value>=11: h.gold+=12; grant(h,'greater'); msg=f'Altar {value}/11 berhasil: +12 gold, Greater Potion.'
            else: h.hp=max(1,h.hp-4); grant(h,'potion'); msg=f'Altar {value}/11 gagal: -4 HP, Health Potion.'
        else: return False,'Tidak ada objek interaktif di sini.'
        p.cleared.append(p.position); return True,msg
    def buy(self,item):
        if self.pending or self.hero.finished or self.feature not in ('shop','entrance') or item not in ITEMS: return False,'Shop tidak tersedia.'
        price=max(1,ITEMS[item].price-self.hero.attrs['CHA'])
        if self.hero.gold<price: return False,'Gold tidak cukup.'
        self.hero.gold-=price; grant(self.hero,item); return True,f'Membeli {ITEMS[item].name}.'
    def use(self,item):
        if self.pending or self.hero.finished: return False,'Tidak bisa menggunakan item di sini.'
        return use_item(self.hero,item)
    def advance(self):
        if self.hero.finished or self.position!=self.map.boss or self.progress.position not in self.progress.cleared: return False,'Kalahkan boss dahulu.'
        self.hero.floor+=1; p=self.progress; p.position='1,1'; p.cleared=[]; p.seen=[]; p.attempts={}; p.events=0; self.hero.restore(); self._generate(); self.reveal()
        return True,'Lantai baru berhasil dibuat.'
