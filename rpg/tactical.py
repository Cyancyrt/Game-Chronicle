"""Deterministic tactical combat, no terminal dependencies. All coordinates are x,y.
Player acts with AP; enemies announce fixed plans, then resolve in stable ID order.
"""
from dataclasses import dataclass, asdict
from math import isfinite
from .combat import Unit, roll
from .gridcombat import GridBattle
from .grid import distance, neighbors, shortest, DIRECTIONS, add
from .items import use_item, count

@dataclass(frozen=True)
class Rules:
    ap: int = 6
    move: int = 1
    attack: int = 2
    skill: int = 3
    ultimate: int = 4
    guard: int = 2
    item: int = 2
    interrupt: int = 3
    hazard_damage: int = 4
    enemy_damage_scale: float = 1.0

    def __post_init__(self):
        for k in ("ap","move","attack","skill","ultimate","guard","item","interrupt","hazard_damage"):
            v=getattr(self,k)
            if type(v) is not int or v<=0 or (k not in ("ap","hazard_damage") and v>self.ap): raise ValueError(f"Invalid rule: {k}")
        if not isfinite(self.enemy_damage_scale) or self.enemy_damage_scale<=0: raise ValueError("Invalid enemy damage scale")

ARCHETYPES = {'Low Rank Slime':'Trapper','Skeleton':'Berserker','Goblin':'Assassin',
 'Goblin Warrior':'Guardian','Medium Slime':'Controller','Goblin Archer':'Sniper',
 'Skeleton Armor':'Healer','Goblin Captain':'Commander','Giant Skeleton':'Summoner','Mirror Mimic':'Mimic'}
TERRAIN = {'fire':'F','ice':'I','poison':'P','spike':'^','barrel':'O','heal':'+','abyss':'X','oil':'~','water':'W','wall':'%'}
OBJECTIVES = ('elimination','survival','escape','assassination','capture','ritual','treasure','defense','reinforcement')

class TacticalBattle(GridBattle):
    def __init__(self,hero,names,tier,boss=False,rng=None,objective='elimination',rules=None):
        self.rules=rules or Rules(); self.objective='elimination' if boss else objective
        if self.objective not in OBJECTIVES: raise ValueError('unknown objective')
        self.tier=tier; self.plans={}; self.cancelled=set(); self.interrupt_until={}; self.ap=0; self.phase=1
        self.terrain={}; self.goal=(1,1); self.goal_progress=0; self.initial_enemies=len(names)
        self.metrics=dict(actions=0,ap_spent=0,damage_dealt=0,damage_taken=0,telegraphs_hit=0,telegraphs_avoided=0,interrupts=0,reactions=0,items=0)
        self.object_hp=18; self.summoned=0; self.guarded=False; self.last_action=None
        super().__init__(hero,names,tier,boss,rng)
    def _setup_positions(self):
        super()._setup_positions()
        self.goal=(7,3) if self.objective=='escape' else (1,1) if self.objective=='defense' else (4,3)
        self.walls.discard(self.goal); self.cover.discard(self.goal)
        reserved={self.goal,self.player.pos,*(e.pos for e in self.enemies),*self.walls,*self.cover}
        pool=[(x,y) for y in range(self.height) for x in range(self.width) if (x,y) not in reserved and x>=2]
        self.rng.shuffle(pool)
        for p,t in zip(pool,('fire','ice','poison','spike','barrel','heal','oil','water','wall','abyss')): self.terrain[p]=t
        # Solid terrain must not cut any spawn or objective off.
        for p in sorted(self.terrain):
            if self.terrain[p] in ('wall','abyss','barrel') and any(shortest(self.player.pos,lambda q:q==g,self.walkable) is None for g in [self.goal,*(e.pos for e in self.enemies)]): self.terrain[p]='spike'
    def walkable(self,p):
        return super().walkable(p) and self.terrain.get(p) not in ('wall','abyss','barrel')
    def los(self,a,b):
        # Integer supercover: diagonal corner is blocked if either crossed side is solid.
        x,y=a; dx=b[0]-x; dy=b[1]-y; nx,ny=abs(dx),abs(dy); sx=1 if dx>0 else -1; sy=1 if dy>0 else -1; ix=iy=0
        def solid(p): return p in self.walls or self.terrain.get(p)=='wall'
        while ix<nx or iy<ny:
            d=(1+2*ix)*ny-(1+2*iy)*nx
            if d==0:
                if solid((x+sx,y)) or solid((x,y+sy)): return False
                x+=sx; y+=sy; ix+=1; iy+=1
            elif d<0: x+=sx; ix+=1
            else: y+=sy; iy+=1
            if (x,y)!=b and solid((x,y)): return False
        return True
    def archetype(self,e): return 'Boss' if self.boss and e is self.enemies[0] else ARCHETYPES.get(e.name,'Berserker')
    def _damage(self,target,amount):
        n=super()._damage(target,max(0,int(amount)))
        self.metrics['damage_taken' if target is self.player else 'damage_dealt']+=n
        return n
    def _end_check(self):
        p=self.player
        if self.result=='ongoing':
            if not p.alive or (self.objective=='defense' and self.object_hp<=0): self.result='defeat'
            elif not self.living and self.objective=='elimination': self.result='victory'
            elif self.objective in ('assassination','ritual') and not self.enemies[0].alive: self.result='victory'
            elif self.objective=='escape' and p.pos==self.goal: self.result='victory'
            elif self.objective=='treasure' and self.goal_progress and p.pos==(1,1): self.result='victory'
        self.hero.hp=p.hp
        return self.result!='ongoing'
    def _advance(self):
        # Base constructor calls this once; new system deliberately removes surprise opening attacks.
        self.order=[self.player,*self.enemies]; self.index=0
        self.log[-1]='Tactical initiative: player plans first; enemy intents resolve by ID.'
        self._start_round()
    def _start_round(self):
        if self._end_check(): return
        ready=self._begin(self.player); self.ap=self.rules.ap if ready else max(1,self.rules.ap//2)
        if not ready: self.log.append('Stun: AP berkurang, bukan kehilangan seluruh giliran.')
        self.steps_left=self.ap; self.guarded=False; self.cancelled.clear()
        if self.boss:
            e=self.enemies[0]; phase=3 if e.hp*10<=e.max_hp*3 else 2 if e.hp*10<=e.max_hp*7 else 1
            if phase>self.phase:
                self.phase=phase; self.log.append(f'BOSS PHASE {phase}!')
        if self.boss and self.phase==3:
            ring=min(2,1+self.round//6)
            for y in range(self.height):
                for x in range(self.width):
                    q=(x,y)
                    if min(x,y,self.width-1-x,self.height-1-y)<ring and self.walkable(q) and q not in (self.goal,self.player.pos): self.terrain[q]='fire'
        self.plans={i:self._plan(e) for i,e in enumerate(self.enemies) if e.alive}
        self._end_check()
    def _area(self,center,radius=1):
        return { (x,y) for y in range(self.height) for x in range(self.width) if max(abs(x-center[0]),abs(y-center[1]))<=radius and self.los(center,(x,y)) and (x,y) not in self.walls }
    def _line(self,a,b,length):
        dx,dy=b[0]-a[0],b[1]-a[1]; d=(1 if dx>=0 else -1,0) if abs(dx)>=abs(dy) else (0,1 if dy>=0 else -1)
        out=set(); q=a
        for _ in range(length):
            q=add(q,d)
            if not (0<=q[0]<self.width and 0<=q[1]<self.height) or q in self.walls or self.terrain.get(q)=='wall': break
            out.add(q)
        return out
    def _plan(self,e):
        role=self.archetype(e); p=self.player; idx=self.enemies.index(e); origin=e.pos
        damage=max(1,round((e.damage+e.die/2)*self.rules.enemy_damage_scale)); kind='strike'; name=e.ability; cells=set(); dest=None; target=None
        if role=='Healer' and self.round%3==0 and any(u.hp<u.max_hp for u in self.living):
            target=min((i for i,u in enumerate(self.enemies) if u.alive and u.hp<u.max_hp),key=lambda i:self.enemies[i].hp/self.enemies[i].max_hp); kind='heal'; name='Grave Mend'
        elif role in ('Guardian','Commander') and self.round%3==0: kind='support'; name='Protect allies'
        elif (role=='Summoner' or (role=='Boss' and self.phase>=2)) and self.round%3==0 and self.summoned<2: kind='summon'; name='Raise minion'
        elif role=='Boss' and self.phase>=2 and self.round%2==0:
            cells=self._area(p.pos,1 if self.phase==2 else 2); damage+=4; name='Cataclysm'; kind='strike'
        elif role=='Mimic' and self.last_action=='guard': kind='support'; name='Echo guard'
        elif role=='Mimic' and self.last_action=='skill' and e.distance(p)<=3 and self.los(e.pos,p.pos): cells=self._area(p.pos,1); name='Echo spell'
        elif role=='Controller' and e.distance(p)<=3 and self.los(e.pos,p.pos): cells=self._area(p.pos,1); name='Crushing field'
        elif role=='Sniper' and e.distance(p)<=1:
            options=[q for q in neighbors(e.pos) if self.free(q,e) and distance(q,p.pos)>e.distance(p)]
            if options: kind='move'; name='Retreat'; dest=options[0]; cells={dest}
            else: cells={p.pos}
        elif role=='Sniper' and e.distance(p)<=e.reach and self.los(e.pos,p.pos):
            cells=self._line(e.pos,p.pos,e.reach+1)
            if p.pos not in cells: cells={p.pos} # precise shot at non-cardinal target
            name='Piercing shot'; damage+=2
        elif e.distance(p)<=e.reach and self.los(e.pos,p.pos):
            cells={p.pos}; name='Marked strike'
            if role in ('Berserker','Boss') and self.round%2==0: cells={q for q in neighbors(e.pos) if self.walkable(q)}|{p.pos}; name='Cleave'; damage+=2
            if role=='Berserker' and e.hp*2<=e.max_hp: damage+=3
            if role=='Trapper': kind='trap'; name='Acid trap'
        else:
            kind='move'; name='Flank' if role=='Assassin' else 'Advance'
            path=shortest(e.pos,lambda q:distance(q,p.pos)<=e.reach and self.los(q,p.pos),lambda q:self.free(q,e))
            if path:
                dest=path[min(len(path),2)-1]; cells={dest}
                if len(path)<=2 and role in ('Assassin','Berserker','Boss','Guardian'):
                    kind='charge'; name='Lunge'; cells={p.pos}; damage+=1
            else: name='Wait'
        if self.objective=='defense' and self.round%2==0 and idx==0: kind='siege'; cells={self.goal}; name='Attack relic'; damage=10
        return {'name':name,'kind':kind,'cells':sorted(cells),'damage':damage if kind in ('strike','trap','siege','charge') else 0,'origin':origin,'destination':dest,'target':target}
    def intent(self,e): return self.plans.get(self.enemies.index(e),{}).get('name','None')
    def _spawn(self):
        options=[q for y in range(self.height) for x in range(self.width) if self.free(q:=(x,y),None) and distance(q,self.player.pos)>=3 and q!=self.goal]
        if not options or self.summoned>=4: return
        q=max(options,key=lambda z:distance(z,self.player.pos)); self.enemies.append(Unit('Skeleton',12,12,10,3,2,4,1,1,q)); self.summoned+=1; self.log.append('Skeleton reinforcement!')
    def _terrain_enter(self,u,previous=None,slide=True):
        t=self.terrain.get(u.pos)
        if t=='fire': self._damage(u,self.rules.hazard_damage); u.conditions['burn']=2
        elif t=='spike': self._damage(u,self.rules.hazard_damage)
        elif t=='poison': u.conditions['poison']=3
        elif t=='water': u.conditions['wet']=2; u.conditions.pop('burn',None)
        elif t=='oil': u.conditions['oil']=2
        elif t=='heal': u.hp=min(u.max_hp,u.hp+8); self.terrain.pop(u.pos,None)
        elif t=='ice' and previous is not None and slide:
            q=add(u.pos,(u.pos[0]-previous[0],u.pos[1]-previous[1]))
            if self.free(q,u): old=u.pos; u.pos=q; self._terrain_enter(u,old,False)
        if t: self.log.append(f'{u.name}: {t} at {u.pos}.')
    def _dash(self,target):
        old=self.player.pos; super()._dash(target)
        if old!=self.player.pos: self._terrain_enter(self.player,old,False)
    def _push(self,e):
        options=[q for q in neighbors(e.pos) if distance(q,self.player.pos)>e.distance(self.player)]
        for q in options:
            if self.terrain.get(q)=='abyss': self._damage(e,12); self.log.append('Abyss impact!'); return
            if self.free(q,e): old=e.pos; e.pos=q; self._terrain_enter(e,old); self.cancelled.add(self.enemies.index(e)); return
    def _attack(self,attacker,target,*args,**kwargs):
        if not self.los(attacker.pos,target.pos): return False
        return super()._attack(attacker,target,*args,**kwargs)
    def _spend(self,n):
        self.ap-=n; self.steps_left=self.ap; self.metrics['ap_spent']+=n; self.metrics['actions']+=1
        self._end_check()
    def move(self,dest,safe=False):
        cost=self.rules.move+(1 if safe else 0); p=self.player
        if self.result!='ongoing' or self.ap<cost or 'slow' in p.conditions or 'frozen' in p.conditions: return False,'Gerak tidak tersedia / AP kurang.'
        if not isinstance(dest,tuple) or len(dest)!=2 or distance(p.pos,dest)!=1 or not self.free(dest,p): return False,'Petak tidak valid.'
        # No free opportunity attacks: announced threats should be dodgeable.
        old=p.pos; p.pos=dest; self._terrain_enter(p,old)
        if safe: p.barrier=max(p.barrier,3)
        if self.objective=='treasure' and p.pos==self.goal: self.goal_progress=1; self.log.append('Treasure secured! Return to (1,1).')
        self._spend(cost); return True,f'Move {p.pos}; AP {self.ap}.'
    def skill_cost(self,s): return self.rules.ultimate if s.level>=7 else self.rules.skill
    def skill_reason(self,s): return super().skill_reason(s) or ('AP tidak cukup.' if self.ap<self.skill_cost(s) else '')
    def pattern(self,s):
        if not s.dice[0]: return 'self'
        return {'Fireball':'burst','Meteor':'burst','Volley':'burst','Whirlwind':'ring','Blade Storm':'ring','Chain Lightning':'chain','Frost Lance':'line','Impale':'line'}.get(s.name,'single')
    def skill_cells(self,s,target=None):
        pat=self.pattern(s); p=self.player.pos
        if pat=='self': return {p}
        if pat=='ring': return {q for q in neighbors(p) if 0<=q[0]<self.width and 0<=q[1]<self.height and q not in self.walls and self.los(p,q)}
        if target is None: return set()
        q=target.pos if hasattr(target,'pos') else target
        if pat=='burst': return self._area(q)
        if pat=='line': return self._line(p,q,s.reach) if p[0]==q[0] or p[1]==q[1] else set()
        if pat=='chain':
            cells={q}; current=q
            for _ in range(2):
                opts=sorted(e.pos for e in self.living if e.pos not in cells and distance(current,e.pos)<=2 and self.los(current,e.pos))
                if not opts: break
                current=opts[0]; cells.add(current)
            return cells
        return {q}
    def valid_target(self,q,reach): return isinstance(q,tuple) and len(q)==2 and all(type(v) is int for v in q) and 0<=q[0]<self.width and 0<=q[1]<self.height and distance(self.player.pos,q)<=reach and self.los(self.player.pos,q)
    def _reaction(self,e,s):
        status=e.conditions
        if s.name in ('Fireball','Meteor'):
            if 'oil' in status or 'poison' in status:
                status.pop('oil',None); status.pop('poison',None); self._damage(e,6); self.metrics['reactions']+=1; self.log.append('Combustion +6!')
            if 'frozen' in status: status.pop('frozen'); self._damage(e,4); self.metrics['reactions']+=1
            if e.alive: status['burn']=2
        if s.name=='Frost Lance' and 'wet' in status: status.pop('wet'); status['frozen']=1; self.metrics['reactions']+=1; self.log.append('Freeze: intent cancelled.')
        if s.name=='Chain Lightning' and 'wet' in status: self._damage(e,5); status.pop('wet'); self.metrics['reactions']+=1
    def _cast_tactical(self,s,target,cell):
        reason=self.skill_reason(s)
        if reason: return False,reason
        pat=self.pattern(s); p=self.player; q=target.pos if target is not None else cell
        if pat in ('single','chain','line') and (target not in self.living or not self.valid_target(target.pos,s.reach)): return False,'Target di luar range / LOS.'
        if pat=='line' and p.pos[0]!=q[0] and p.pos[1]!=q[1]: return False,'Line membutuhkan target satu baris/kolom.'
        if pat=='burst' and (q is None or not self.valid_target(q,s.reach) or q in self.walls): return False,'Pusat area di luar range / LOS.'
        if pat in ('single','self'):
            ok,msg=super()._cast(s,target)
            if ok and target is not None and s.effect=='stun' and 'stun' in target.conditions: self.cancelled.add(self.enemies.index(target))
            return ok,msg
        cells=self.skill_cells(s,q); targets=[e for e in self.living if e.pos in cells]
        if not targets and not any(self.terrain.get(c) in ('barrel','wall') for c in cells): return False,'Area kosong; arah line harus kardinal.'
        setattr(self.hero,s.kind,getattr(self.hero,s.kind)-s.cost); self.cooldowns[s.name]=p.turns+s.cooldown+1
        self.log.append(f'{s.name} / {pat}')
        for e in targets:
            if not p.alive: break
            if s.effect=='area_save':
                dmg=roll(self.rng,*s.dice)+p.damage; self._damage(e,dmg//2 if self._check(e,10+self.hero.attack) else dmg); hit=True
            else: hit=self._attack(p,e,s.dice)
            if hit and e.alive:
                if s.effect in ('slow','bleed'): e.conditions[s.effect]=2 if s.effect=='bleed' else 1
                self._reaction(e,s)
        for c in sorted(cells):
            if self.terrain.get(c) in ('barrel','wall'): self._break(c)
        return True,''
    def _break(self,q):
        t=self.terrain.pop(q,None)
        if t=='barrel':
            for u in [self.player,*self.living]:
                if u.alive and distance(u.pos,q)<=1: self._damage(u,8)
            self.terrain[q]='fire'; self.log.append('Barrel explosion!')
        else: self.log.append('Destructible wall broken.')
    def act(self,action,target=None,skill=None,dest=None,item=None,cell=None):
        if self.result!='ongoing': return False,'Battle selesai.'
        p=self.player; h=self.hero; r=self.rules
        if action=='end': self._end_round(); return True,'End turn.'
        if action=='disengage': return self.move(dest,True)
        costs={'attack':r.attack,'skill':self.skill_cost(skill) if skill else r.skill,'guard':r.guard,'item':r.item,'interrupt':r.interrupt,'heavy':r.skill,'flee':r.ap,'break':r.attack}
        if action not in costs or self.ap<costs[action]: return False,'Aksi tidak dikenal / AP kurang.'
        if action in ('attack','heavy','interrupt'):
            if target not in self.living or not self.valid_target(target.pos,p.reach if action=='attack' else 1): return False,'Target di luar range / LOS.'
            if action=='interrupt':
                i=self.enemies.index(target)
                if i in self.cancelled or self.round<self.interrupt_until.get(i,0) or self.plans.get(i,{}).get('kind') not in ('strike','trap','summon','heal','siege','charge'): return False,'Tidak ada intent yang dapat di-interrupt.'
                self.cancelled.add(i); self.interrupt_until[i]=self.round+2; self.metrics['interrupts']+=1; self._damage(target,2); self.log.append(f'Interrupted {target.name}!')
            elif action=='heavy':
                if self._attack(p,target,(2,p.die)) and target.alive:
                    if target.conditions.pop('frozen',None): self._damage(target,6); self.metrics['reactions']+=1
                    else: target.barrier=0; target.conditions.pop('guard',None); self._push(target)
            else: self._attack(p,target)
        elif action=='skill':
            if skill is None: return False,'Pilih skill.'
            ok,msg=self._cast_tactical(skill,target,cell)
            if not ok: return False,msg
        elif action=='guard':
            if self.guarded: return False,'Guard hanya sekali per giliran.'
            p.conditions['guard']=1; p.conditions.pop('slow',None); self.guarded=True; h.stamina=min(h.max_stamina,h.stamina+2)
        elif action=='item':
            if item=='bomb':
                targets=[e for e in self.living if self.valid_target(e.pos,2)]
                if count(h,'bomb')<=0 or not targets: return False,'Bomb tidak tersedia / target tidak terlihat.'
                from .items import grant
                for e in targets: self._damage(e,10)
                grant(h,'bomb',-1)
            else:
                ok,msg=use_item(h,item,self)
                if not ok: return False,msg
            self.metrics['items']+=1
        elif action=='break':
            if not self.valid_target(cell,p.reach) or self.terrain.get(cell) not in ('barrel','wall'): return False,'Objek di luar range / LOS.'
            self._break(cell)
        elif action=='flee': self.result='fled'; h.hp=p.hp
        self.last_action=action; self._spend(costs[action]); return True,f'{action}: AP {self.ap}.'
    def _tick_status(self,e):
        e.conditions.pop('slow',None)
        for k in ('poison','corrode','wet','oil'):
            if k in e.conditions:
                e.conditions[k]-=1
                if e.conditions[k]<=0: e.conditions.pop(k,None)
    def _end_round(self):
        p=self.player
        for i,plan in list(self.plans.items()):
            if self._end_check(): return
            e=self.enemies[i]
            if not e.alive: continue
            observer = getattr(self, '_presentation_observer', None)
            if observer: observer('before', i, plan)
            try:
                ready=self._begin(e)
                frozen=e.conditions.pop('frozen',0)
                if not ready or i in self.cancelled or frozen:
                    self._tick_status(e)
                    self.log.append(f'{e.name}: intent cancelled.'); continue
                kind=plan['kind']; cells=set(plan['cells'])
                if kind in ('strike','trap','siege','charge'):
                    # Forced displacement cancels anchored attacks; tile targets never track hero.
                    if e.pos!=plan['origin']: self.log.append(f'{e.name}: displaced, attack cancelled.'); self._tick_status(e); continue
                    if kind=='charge':
                        q=plan['destination']; path=shortest(e.pos,lambda z:z==q,lambda z:self.free(z,e))
                        if not path or len(path)>2 or 'slow' in e.conditions: self._tick_status(e); continue
                        for step in path:
                            old=e.pos; e.pos=step; self._terrain_enter(e,old)
                            if not e.alive or e.pos!=step: break
                        if not e.alive or e.pos!=q: self._tick_status(e); continue
                    if kind=='siege': self.object_hp-=plan['damage']
                    elif p.pos in cells and self.los(e.pos,p.pos):
                        dmg=max(1,plan['damage']-max(0,(p.armor-12)//2)); dmg=(dmg+1)//2 if 'guard' in p.conditions or 'dodge' in p.conditions else dmg
                        if 'stealth' in p.conditions: dmg=(dmg+1)//2
                        if p.pos in self.cover and distance(e.pos,p.pos)>1: dmg=max(1,dmg-2)
                        self._damage(p,dmg); self.metrics['telegraphs_hit']+=1; self.log.append(f'{e.name}: {plan["name"]} hits {dmg}.')
                        if e.effect in ('bleed','poison','corrode','stun') and p.alive: p.conditions[e.effect]=1 if e.effect=='stun' else 2
                        if 'counter' in p.conditions and p.alive and p.distance(e)<=1: p.conditions.pop('counter'); self._attack(p,e)
                    else: self.metrics['telegraphs_avoided']+=1; self.log.append(f'{e.name}: attack avoided.')
                    if kind=='trap':
                        for q in cells:
                            if self.walkable(q) and q!=self.goal: self.terrain[q]='poison'
                elif kind=='move' and plan['destination'] is not None and 'slow' not in e.conditions:
                    q=plan['destination']; path=shortest(e.pos,lambda z:z==q,lambda z:self.free(z,e))
                    if path and len(path)<=2:
                        for step in path:
                            if not e.alive: break
                            old=e.pos; e.pos=step; self._terrain_enter(e,old)
                            if e.pos!=step: break
                elif kind=='heal':
                    u=self.enemies[plan['target']]
                    if u.alive: u.hp=min(u.max_hp,u.hp+8)
                elif kind=='support':
                    for u in self.living: u.barrier=max(u.barrier,4)
                elif kind=='summon': self._spawn()
                self._tick_status(e)
            finally:
                if observer: observer('after', i, plan)
        if self._end_check(): return
        p.conditions.pop('slow',None)
        for k in ('poison','corrode','wet','oil','frozen'):
            if k in p.conditions:
                p.conditions[k]-=1
                if p.conditions[k]<=0: p.conditions.pop(k,None)
        if self.objective in ('survival','defense') and self.round>=5: self.result='victory'
        elif self.objective=='capture':
            self.goal_progress=self.goal_progress+1 if p.pos==self.goal else 0
            if self.goal_progress>=2: self.result='victory'
        elif self.objective=='ritual' and self.round>=6: self.result='defeat'
        elif self.objective=='reinforcement':
            if not self.living and self.summoned>=2: self.result='victory'
            elif not self.living or self.round in (2,4): self._spawn()
        if self._end_check(): return
        self.round+=1; self._start_round()
    def observation(self):
        return {'ap':self.ap,'max_ap':self.rules.ap,'phase':self.phase,'last_action':self.last_action,'objective':self.objective,'goal':list(self.goal),'goal_progress':self.goal_progress,'interrupt_until':dict(self.interrupt_until),'object_hp':self.object_hp,'terrain':{f'{x},{y}':t for (x,y),t in sorted(self.terrain.items())},'plans':{str(i):dict(plan) for i,plan in self.plans.items() if self.enemies[i].alive and i not in self.cancelled},'metrics':dict(self.metrics),'rules':asdict(self.rules),'archetypes':{str(i):self.archetype(e) for i,e in enumerate(self.enemies) if e.alive}}
