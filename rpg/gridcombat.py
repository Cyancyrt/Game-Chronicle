"""Tactical combat; original dice, skills, initiative and statuses are inherited."""
from .combat import Battle
from .grid import distance, shortest, neighbors
from .items import use_item

class GridBattle(Battle):
    width, height = 9, 7
    def _setup_positions(self):
        self.player.pos=(1,3); self.steps_left=2
        slots=[(6,3),(7,1),(7,5),(5,1)]
        for i,e in enumerate(self.enemies): e.pos=slots[i]
        reserved={self.player.pos,*(e.pos for e in self.enemies)}
        self.walls=set(); self.cover=set()
        candidates=[(x,y) for y in range(1,6) for x in range(2,7) if (x,y) not in reserved]
        self.rng.shuffle(candidates)
        for p in candidates[:self.rng.randint(2,6)]:
            self.walls.add(p)
            if any(shortest(self.player.pos,lambda q:q==e.pos,self.walkable) is None for e in self.enemies): self.walls.remove(p)
        self.cover=set(self.rng.sample([p for p in candidates if p not in self.walls], 3))
    def walkable(self,p):
        return 0<=p[0]<self.width and 0<=p[1]<self.height and p not in self.walls
    def free(self,p,unit):
        return self.walkable(p) and all(u is unit or u.pos!=p for u in [self.player,*self.living])
    def _reset_movement(self): self.steps_left=2
    def _enemy_move(self,enemy):
        path=shortest(enemy.pos,lambda p:distance(p,self.player.pos)<=enemy.reach,lambda p:self.free(p,enemy))
        if path:
            enemy.pos=path[min(2,len(path))-1]
            self.log.append(f'{enemy.name} bergerak ke {enemy.pos}.')
    def move(self,dest,safe=False):
        p=self.player
        if self.result!='ongoing' or self.steps_left<=0 or 'slow' in p.conditions:
            return False,'Gerakan tidak tersedia.'
        if not isinstance(dest,tuple) or len(dest)!=2 or distance(p.pos,dest)!=1 or not self.free(dest,p):
            return False,'Pilih satu petak bebas yang bersebelahan.'
        for e in self.living:
            if not safe and e.reach<=2 and e.reaction and e.distance(p)<=e.reach<distance(e.pos,dest):
                e.reaction=False; self.log.append(f'Opportunity Attack: {e.name}!'); self._attack(e,p)
                if self._end_check(): return True,'Tumbang saat bergerak.'
        p.pos=dest; self.steps_left-=1; self.moved=self.steps_left==0
        return True,f'Posisi {dest}; sisa gerak {self.steps_left}.'
    def _cast(self,skill,target):
        if skill.effect=="dash" and target in self.living and self.player.distance(target)>1:
            path=shortest(self.player.pos,lambda q:distance(q,target.pos)==1,lambda q:self.free(q,self.player))
            if not path or len(path)>skill.reach: return False,"Jalur dash terhalang."
        return super()._cast(skill,target)
    def _dash(self,target):
        p=self.player
        if p.distance(target)<=1: return
        path=shortest(p.pos,lambda q:distance(q,target.pos)==1,lambda q:self.free(q,p))
        if path and len(path)<=4: p.pos=path[-1]
    def _push(self,enemy):
        options=[q for q in neighbors(enemy.pos) if self.free(q,enemy) and distance(q,self.player.pos)>enemy.distance(self.player)]
        if options: enemy.pos=options[0]
    def act(self,action,target=None,skill=None,dest=None,item=None):
        if action!='item': return super().act(action,target,skill,dest)
        if self.result!='ongoing': return False,'Pertarungan sudah berakhir.'
        ok,msg=use_item(self.hero,item,self)
        if ok:
            self.log.append(msg); self._finish_turn(self.player)
            if self.result=='ongoing': self._advance()
        return ok,msg
