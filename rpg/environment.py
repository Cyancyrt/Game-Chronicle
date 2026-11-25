"""Minimal headless experiment interface (not a Gymnasium implementation).
Observation exposes visible map only; full latent state lives in dungeon.
No rendering, no input(), no file writes. One step = one command.
"""
from copy import deepcopy
from .models import Hero
from .procedural import ProceduralDungeon,Progress,key
from .grid import DIRECTIONS,add
from .items import ITEMS,count

class DungeonEnv:
    def __init__(self,seed=0,class_name='Swordsman',floors=10,max_steps=10000,mode='tactical',rules=None):
        self.mode=mode; self.rules=rules; self.floors=floors; self.max_steps=max_steps; self.reset(seed,class_name)
    def reset(self,seed=0,class_name='Swordsman'):
        if not 5<=self.floors<=50: raise ValueError('floors must be 5..50')
        h=Hero.create('Agent',class_name); h.inventory={'ether':1,'ration':1}
        self.dungeon=ProceduralDungeon(h,Progress(seed,self.floors),mode=self.mode,rules=self.rules); self.steps=0; self.battle=None
        return self.observe()
    def observe(self):
        d=self.dungeon; h=d.hero; m=d.map; b=self.battle; seen=set(d.progress.seen); cleared=set(d.progress.cleared)
        tiles={key(p):('cleared' if key(p) in cleared else m.features.get(p,'floor')) if p in m.tiles else 'wall' for p in [(x,y) for x in range(m.width) for y in range(m.height)] if key(p) in seen}
        obs={'floor':h.floor,'total_floors':d.progress.total,'position':list(d.position),'seals':d.seals,'shape':[m.height,m.width],'visible_tiles':tiles,'hero':{'class':h.class_name,'level':h.level,'hp':h.hp,'max_hp':h.max_hp,'mana':h.mana,'stamina':h.stamina,'gold':h.gold,'xp':h.xp,'points':h.points,'attributes':dict(h.attrs)},'inventory':{k:count(h,k) for k in ITEMS},'mode':'combat' if b else 'exploration'}
        if b:
            def unit(u): return {'name':u.name,'hp':u.hp,'max_hp':u.max_hp,'position':list(u.pos),'range':u.reach,'ac':u.armor,'status':dict(u.conditions),'barrier':u.barrier}
            obs['battle']={'round':b.round,'turn':b.player.turns,'player':unit(b.player),'enemies':[{'id':i,**unit(e),'intent':b.intent(e)} for i,e in enumerate(b.enemies) if e.alive],'walls':sorted(b.walls),'cover':sorted(b.cover),'steps_left':b.steps_left,'skills':[{'id':i,'name':s.name,'range':s.reach,'effect':s.effect,'cost':s.cost,'resource':s.kind,'unavailable':b.skill_reason(s)} for i,s in enumerate(h.skills)]}
            if hasattr(b,"observation"):
                obs["battle"].update(b.observation())
                for entry,s in zip(obs["battle"]["skills"],h.skills): entry.update(ap=b.skill_cost(s),pattern=b.pattern(s))
        return deepcopy(obs)
    def step(self,action):
        if self.dungeon.hero.finished or self.steps>=self.max_steps: raise RuntimeError('Episode ended; reset required.')
        battle_metrics=None; battle_result=None; self.steps+=1; d=self.dungeon; h=d.hero; b=self.battle; op=action.get('action'); ok=False; msg='Invalid action'; reward=-.01
        if b:
            target_id=action.get('target'); target=b.enemies[target_id] if type(target_id) is int and 0<=target_id<len(b.enemies) else None
            skill_id=action.get('skill'); skill=h.skills[skill_id] if type(skill_id) is int and 0<=skill_id<len(h.skills) else None
            if op in ('move','disengage') and action.get('direction') in DIRECTIONS:
                dest=add(b.player.pos,DIRECTIONS[action['direction']]); ok,msg=b.move(dest) if op=='move' else b.act('disengage',dest=dest)
            elif hasattr(b,'observation') and op in ('attack','skill','guard','flee','item','end','heavy','interrupt','break'):
                raw=action.get('cell'); cell=tuple(raw) if isinstance(raw,(list,tuple)) and len(raw)==2 and all(type(v) is int for v in raw) else None
                ok,msg=b.act(op,target,skill,item=action.get('item'),cell=cell)
            elif op in ('attack','skill','guard','flee','item'): ok,msg=b.act(op,target,skill,item=action.get('item'))
        else:
            if op=='move': ok,msg=d.move(action.get('direction'))
            elif op=='interact': ok,msg=d.interact(action.get('attribute','WIS'))
            elif op=='buy': ok,msg=d.buy(action.get('item'))
            elif op=='item': ok,msg=d.use(action.get('item'))
            elif op=='advance': ok,msg=d.advance(); reward+=2 if ok else 0
            elif op=='allocate': ok=h.allocate(action.get('attribute')); msg='Attribute allocation'
            if d.pending: self.battle=d.encounter()
        if self.battle and self.battle.result!='ongoing':
            result=self.battle.result; battle_result=result; battle_metrics=getattr(self.battle,'metrics',None); msg+=' | '+' '.join(d.resolve(self.battle)); self.battle=None
            reward+= {'victory':1,'defeat':-2,'fled':-.5}[result]
        if not ok: reward-=.1
        if h.finished: reward+=10
        return self.observe(),reward,h.finished,self.steps>=self.max_steps and not h.finished,{'valid':ok,'message':msg,'battle_metrics':battle_metrics,'battle_result':battle_result}
