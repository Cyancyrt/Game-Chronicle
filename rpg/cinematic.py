"""Read-only battle presentation. No RNG, damage calculation or engine actions here."""
from dataclasses import dataclass
import sys
import time
from .sprites import HEROES, ENEMIES, SKELETON, pose
from .ui import safe, wrap

@dataclass(frozen=True)
class UnitView:
    name: str
    sprite: str
    hp: int
    max_hp: int
    barrier: int
    pos: tuple

@dataclass(frozen=True)
class View:
    units: dict
    ap: int
    round: int
    result: str
    mana: int
    stamina: int
    relic: int


def capture(b):
    def unit(u, sprite):
        return UnitView(safe(u.name), sprite, u.hp, u.max_hp, u.barrier, u.pos)
    return View({-1:unit(b.player,b.hero.class_name), **{i:unit(e,e.name) for i,e in enumerate(b.enemies)}},
                b.ap,b.round,b.result,b.hero.mana,b.hero.stamina,b.object_hp)


def focus(b, cursor=None, preferred=None):
    for i,e in enumerate(b.enemies):
        if e.alive and e.pos == cursor: return i
    if preferred is not None and preferred < len(b.enemies) and b.enemies[preferred].alive: return preferred
    return next((i for i,e in enumerate(b.enemies) if e.alive), None)


def sprite_for(view, idx):
    return HEROES[view.sprite] if idx == -1 else ENEMIES.get(view.sprite,SKELETON)


def stage(ui, view, enemy=None, hero_pose='idle', enemy_pose='idle', hero_shift=0,
          enemy_shift=0, step=0, fx='', fx_at=None, caption='', tone='cyan', width=None):
    """A fixed-size stage. Actors move within it; map coordinates remain in the HUD."""
    w=max(20,(width or ui.width)-4)
    if w<32: return [ui.paint('CINEMATIC / '+view.units[-1].sprite,'cyan'), *wrap(caption,w)]
    p=view.units[-1]; e=view.units.get(enemy); ps=sprite_for(p,-1); es=sprite_for(e,enemy) if e else None
    a=max(0,min(w-13,1+hero_shift)); z=max(0,min(w-13,w-14+enemy_shift))
    # Keep both silhouettes visible even on a narrow stage.
    if a+13>z: a=max(0,z-13)
    canvas=[[' ']*w for _ in range(7)]; colors=[['muted']*w for _ in range(7)]
    def put(y,x,s,c):
        for j,ch in enumerate(s):
            if 0<=x+j<w and ch!=' ':
                canvas[y][x+j]=ch; colors[y][x+j]=c
    for y in range(7):
        if y in (0,1):
            for x in range(3,w,13): put(y,x,'.','muted')
        if y==5:
            for x in range(0,w,17): put(y,x,'|','muted')
    for y,r in enumerate(pose(ps,'down' if p.hp<=0 and hero_pose=='idle' else hero_pose,step=step)):
        put(y,a,r,ps.tone)
    if es:
        for y,r in enumerate(pose(es,'down' if e.hp<=0 and enemy_pose=='idle' else enemy_pose,flip=True,step=step)):
            put(y,z,r,es.tone)
    if fx:
        x=fx_at if fx_at is not None else (w-len(fx))//2
        put(3,x,fx,tone)
    def colored(row,tones):
        out=[]; start=0
        for i in range(1,len(row)+1):
            if i==len(row) or tones[i]!=tones[start]:
                out.append(ui.paint(''.join(row[start:i]),tones[start])); start=i
        return ''.join(out)
    title=p.sprite.upper(); enemy_name=(f'#{enemy+1} {e.name.upper()}' if e else 'NO TARGET')
    half=w//2; title=title[:half]; enemy_name=enemy_name[:w-half]
    labels=ui.paint(title,ps.tone)+' '*(w-len(title)-len(enemy_name))+ui.paint(enemy_name,es.tone if es else 'muted')
    rows=[labels,*[colored(row,tones) for row,tones in zip(canvas,colors)],ui.paint('='*w,'muted')]
    if caption: rows.extend(ui.paint(r,tone) for r in wrap(caption,w))
    return rows


def changes(before,after):
    out=[]
    for i,u in after.units.items():
        old=before.units.get(i); name='Hero' if i==-1 else f'#{i+1} {u.name}'
        if not old: out.append(f'{name} spawned'); continue
        hp=u.hp-old.hp; barrier=u.barrier-old.barrier
        if hp: out.append(f'{name} {hp:+d} HP'+(' / DOWN' if u.hp<=0 else ''))
        if barrier: out.append(f'{name} {barrier:+d} barrier')
        if u.pos!=old.pos: out.append(f'{name} {old.pos}->{u.pos}')
    if after.relic!=before.relic: out.append(f'Relic {after.relic-before.relic:+d} HP')
    if after.mana!=before.mana: out.append(f'MP {after.mana-before.mana:+d}')
    if after.stamina!=before.stamina: out.append(f'ST {after.stamina-before.stamina:+d}')
    if after.ap!=before.ap: out.append(f'AP {before.ap}->{after.ap}')
    return ' | '.join(out) or 'No HP / resource change'


class Animator:
    def __init__(self,ui): self.ui=ui

    @property
    def enabled(self):
        return self.ui.animation and self.ui.ansi and self.ui.clear and self.ui.width>=38 and self.ui.height>=18

    def show(self, view, enemy, label, duration=.065, **kwargs):
        if not self.enabled: return
        ui=self.ui
        rows=stage(ui,view,enemy,**kwargs)
        lines=[ui.paint('DUNGEON CHRONICLES  /  BATTLE MOTION','gold'),
               ui.paint(f'ROUND {view.round:02} | {label}','cyan'),
               *ui.panel('COMBAT STAGE',rows,tone='muted')]
        p=view.units[-1]; e=view.units.get(enemy)
        lines.append('HP '+ui.meter(p.hp,p.max_hp,10,'green')+f' | AP {view.ap}')
        if e: lines.append(f'Enemy #{enemy+1} HP '+ui.meter(e.hp,e.max_hp,10,'red'))
        # Single write, no repeated screen clearing and no cursor left hidden.
        sys.stdout.write('\x1b[H'+'\n'.join(lines[:max(1,ui.height-1)])+'\x1b[J'); sys.stdout.flush()
        time.sleep(duration*self.ui.animation_speed)

    def sequence(self,before,after,actor,enemy,label,kind,logs=()):
        if not self.enabled: return
        ui=self.ui; u=before.units.get(actor); n=after.units.get(actor)
        if u is None or n is None: return
        if enemy is None: enemy=next((i for i,e in before.units.items() if i!=-1 and e.hp>0),None)
        s=sprite_for(u,actor); hero=actor==-1; target=enemy if hero else -1
        other=before.units.get(target); new_other=after.units.get(target)
        hurt=bool(other and new_other and (new_other.hp<other.hp or new_other.barrier<other.barrier))
        if kind=='move' and u.pos==n.pos and u.hp==n.hp: kind='wait'
        if kind=='cancel':
            self.show(before,enemy,label,.12,caption='INTENT CANCELLED',tone='gold')
            self.show(after,enemy,label,.13,caption=changes(before,after)); return
        # Position and pose trajectories are presentation only, never grid movement.
        span=max(0,ui.width-32); direction=1 if hero else -1
        def frame(p='idle',shift=0,step=0,fx='',at=None,react=False,state=before,duration=.065,caption=''):
            kw={'hero_pose':p,'hero_shift':shift*direction} if hero else {'enemy_pose':p,'enemy_shift':shift*direction}
            if react:
                kw.update({'enemy_pose':'hurt','enemy_shift':2} if hero else {'hero_pose':'hurt','hero_shift':-2})
            self.show(state,enemy,label,duration,step=step,fx=fx,fx_at=at,caption=caption,**kw)
        if kind in ('move','flee'):
            travel=min(span,8) if kind=='move' else span
            if kind=='move' and u.pos[0]!=n.pos[0]:
                # Stage is a side-on view; grid displacement is always reported exactly.
                travel=min(span,8*abs(n.pos[0]-u.pos[0]))
            for j,k in enumerate((0,1,2,3,4,5)):
                frame('walk',travel*k//5,step=j,caption=f'MOVING {u.pos} -> {n.pos}' if kind=='move' else 'RETREAT')
        elif kind in ('guard','heal','support','item','summon'):
            frame('ready'); frame('guard' if kind=='guard' else 'strike',fx=' . + . '); frame('guard' if kind=='guard' else 'ready',fx='+ * + * +'); frame('idle',fx=' . + . ')
        elif kind!='wait':
            ranged=s.style in ('arrow','magic','holy')
            frame('ready',0,duration=.09,caption='WIND UP')
            frame('ready',0,fx='..' if ranged else '')
            if ranged:
                token={'arrow':'-->' if hero else '<--','magic':'(*)','holy':'<+>'}[s.style]
                token={'Frost Lance':'==*>','Chain Lightning':'/Z/Z/','Meteor':'oO@>','Fireball':'~(@)','Volley':'>>>'}.get(label,token)
                start=14; end=max(start,ui.width-22)
                for j in range(5):
                    x=start+(end-start)*j//4 if hero else end-(end-start)*j//4
                    frame('strike' if j<2 else 'idle',fx=token,at=x)
            else:
                trajectory={'dash':(0,3,9,10),'thrust':(0,4,7,10),'bash':(1,2,4,7,10),'slam':(2,5,9,10)}.get(s.style,(1,4,7,10))
                for j,k in enumerate(trajectory):
                    frame('walk',span*k//10,step=j,duration=.04 if s.style=='dash' else .075 if s.style=='bash' else .055)
                frame('strike',span,fx={'slash':' / / ','thrust':'====>','dash':'//>>','bash':'[!]', 'slam':'!!'}.get(s.style,'*'),at=max(0,ui.width-20) if hero else 12)
                if label in ('Whirlwind','Blade Storm','Triple Jab'):
                    frame('ready',span-2,fx=' / | \\ '); frame('strike',span,fx='//==>',at=max(0,ui.width-20))
            frame('strike',0 if ranged else span,fx='* *' if hurt else '...',at=max(0,ui.width-20) if hero else 12,react=hurt,duration=.09,caption='IMPACT' if hurt else 'RESOLVE')
            frame('walk' if not ranged else 'idle',span//2 if not ranged else 0,react=hurt,duration=.06)
            if not ranged: frame('walk',span//4,step=1)
        else: frame('idle',duration=.08)
        if hero:
            for i,v in after.units.items():
                if i not in (-1,enemy) and i in before.units and (v.hp<before.units[i].hp or v.barrier<before.units[i].barrier):
                    self.show(before,i,label,.07,hero_pose='strike',enemy_pose='hurt',fx='* *',caption='ADDITIONAL TARGET')
                    self.show(after,i,label,.09,caption=f'#{i+1} {v.name}: {v.hp-before.units[i].hp:+d} HP')
        self.show(after,enemy,label,.18,caption=changes(before,after),tone='gold')

    def finish(self,view,enemy):
        if not self.enabled: return
        label=view.result.upper()
        for i in range(5):
            self.show(view,enemy,label,.10,hero_pose='win' if view.result=='victory' and i%2 else 'down' if view.result=='defeat' else 'idle',caption=label,tone='gold')
