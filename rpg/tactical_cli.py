"""Compact terminal interface for AP combat, with target cursor and pattern preview."""
from collections import deque
from . import cli
from .keys import read_key
from .grid import DIRECTIONS, add
from .tactical import TERRAIN
from .procedural_cli import item_menu, ALIASES
from .cinematic import Animator, capture, stage, focus
from .ui import safe, wrap, cell_width

OBJECTIVE_TEXT={'elimination':'Defeat all enemies','survival':'Survive 5 rounds','escape':'Reach objective $','assassination':'Defeat enemy 1','capture':'Hold $ for 2 end turns','ritual':'Defeat enemy 1 before round 6 ends','treasure':'Collect $ then return to (1,1)','defense':'Protect relic $ for 5 rounds','reinforcement':'Defeat waves (at least 2 reinforcements)'}

def arena(b,cursor=None,preview=None):
    ui=cli.UI; danger={q for i,plan in b.plans.items() if b.enemies[i].alive and i not in b.cancelled and plan['kind'] in ('strike','trap','siege','charge') for q in plan['cells']}
    moving={q for i,plan in b.plans.items() if b.enemies[i].alive and i not in b.cancelled and plan['kind']=='move' for q in plan['cells']}
    enemies={e.pos:str(i+1) for i,e in enumerate(b.enemies) if e.alive}; rows=['    '+' '.join(str(x) for x in range(b.width))]
    for y in range(b.height):
        cells=[]
        for x in range(b.width):
            q=(x,y); ch='@' if q==b.player.pos else enemies.get(q,'#' if q in b.walls else '$' if q==b.goal and b.objective!='elimination' else TERRAIN.get(b.terrain.get(q),'C' if q in b.cover else '.'))
            if q==cursor: ch='?'; tone='cyan'
            elif q in (preview or set()): tone='purple'; ch='*' if ch=='.' else ch
            elif q in danger: tone='red'; ch='!' if ch=='.' else ch
            elif q in moving: tone='gold'; ch='>' if ch=='.' else ch
            else: tone='cyan' if ch=='@' else 'red' if ch.isdigit() else 'gold' if ch in '$OC' else 'green' if ch=='+' else 'muted'
            # Occupied danger tiles are listed explicitly in the intent panel.
            cells.append(ui.paint(ch,tone))
        rows.append(f'{y}   '+' '.join(cells))
    rows+=['@ Hero | # Wall | C Cover | ! Danger | > Move','F Fire I Ice P Poison ^ Spike $ Goal O Barrel','+ Heal ~ Oil W Water % Breakable X Abyss']
    return rows

def detail_screen(b,history,notice='',cursor=None,preview=None,footer=None):
    ui=cli.UI;p=b.player;h=b.hero
    left=[f'{cli.safe(h.name)} | {h.class_name} Lv {h.level}',*cli.resource_lines(h,p.hp),f'AP [{"="*b.ap}{"."*(b.rules.ap-b.ap)}] {b.ap}/{b.rules.ap}',f'AC {p.armor} | Barrier {p.barrier} | {cli.conditions(p)}',OBJECTIVE_TEXT[b.objective],f'Progress {b.goal_progress} | Relic HP {b.object_hp}' if b.objective in ('capture','defense','treasure') else '']
    danger=[i+1 for i,plan in b.plans.items() if b.enemies[i].alive and i not in b.cancelled and plan["kind"] in ("strike","trap","charge") and p.pos in plan["cells"]]
    left.append("DANGER: enemy "+", ".join(map(str,danger)) if danger else "Position clear of marked strikes")
    if hasattr(b,'mechanic'):
        m=b.mechanic
        if m.approach: left.append('Approach rebate: '+('USED' if b.approach_used else 'READY'))
        if m.guard_reduction: left.append(f'Guard mitigation: -{m.guard_reduction} incoming raw damage')
        if m.contact_penalty: left.append(f'Contact penalty: -{m.contact_penalty}% direct damage')
        if m.reach_delta: left.append(f'Basic attack reach: {p.reach}')
        if m.skill_slot>=0: left.append(f'{h.spec.skills[m.skill_slot].name}: {m.skill_ap_delta:+d} AP')
    if hasattr(b,'combos'):
        for combo in b.combos:
            if b.active(combo):
                ids=b.active(combo); marks='self' if -1 in ids else ','.join(str(i+1) for i in sorted(ids))
                left.append(f'COMBO READY: {combo.id} | targets {marks}')
    right=[]
    for i,e in enumerate(b.enemies):
        if not e.alive: continue
        plan=b.plans.get(i,{})
        right.extend([f'{i+1} {e.name} ({b.archetype(e)}) HP {e.hp}/{e.max_hp}',f'  {"CANCELLED" if i in b.cancelled else plan.get("name","Waiting")} | RAW DMG {plan.get("damage",0)}',f'  Tiles: {" ".join(f"{x},{y}" for x,y in plan.get("cells",[])) or "-"}'])
        if plan.get('kind')=='charge': right.append(f'  Lunge to {plan["destination"]}')
        if b.round<b.interrupt_until.get(i,0): right.append('  Interrupt resistance this round')
    lines=ui.pair('HERO / OBJECTIVE',left,'ENEMY INTENTS',right)
    lines+=ui.pair('TACTICAL ARENA',arena(b,cursor,preview),'COMBAT LOG',cli.log_lines(history,5)) if ui.width>=72 else ui.panel('TACTICAL ARENA',arena(b,cursor,preview))+ui.panel('COMBAT LOG',cli.log_lines(history,3))
    r=b.rules
    lines+=ui.panel('COMMANDS',[f'[1] Attack {r.attack} AP  [2] Skill {r.skill}/{r.ultimate}  [3] Guard {r.guard}',f'[4] Heavy {r.skill}  [5] Item {r.item}  [6] Interrupt {r.interrupt}',f'[7] Break object {r.attack}  [8] Log  [9] Flee {r.ap}  [E] End turn'])
    if notice: lines+=ui.panel('NOTICE',[notice])
    ui.screen('Tactical battle',lines,footer or 'ARROW / WASD: move (1 AP) | E: resolve enemy intents | V: status',subtitle=f'ROUND {b.round} | PHASE {b.phase}')

def screen(b,history,notice='',cursor=None,preview=None,footer=None,preferred=None):
    ui=cli.UI; p=b.player; h=b.hero; r=b.rules; idx=focus(b,cursor,preferred)
    danger=[str(i+1) for i,plan in b.plans.items() if b.enemies[i].alive and i not in b.cancelled and plan['kind'] in ('strike','trap','charge') and p.pos in plan['cells']]
    top=f'{safe(h.name)} / {h.class_name} Lv {h.level}  |  AP '+ui.paint('['+'='*b.ap+'.'*(r.ap-b.ap)+f'] {b.ap}/{r.ap}','gold')
    resources=cli.resource_lines(h,p.hp)
    if ui.height<32 and ui.tty:
        resources=['HP '+ui.meter(p.hp,h.max_hp,5,'green')+'  MP '+ui.meter(h.mana,h.max_mana,5,'blue')+'  ST '+ui.meter(h.stamina,h.max_stamina,5,'gold')]
    if sum(cell_width(x) for x in resources)+6<=ui.width-4: resources=['   '.join(resources)]
    status=f'AC {p.armor} | Barrier {p.barrier} | Range {p.reach} | Status: {cli.conditions(p)}'
    lines=ui.panel('PLAYER / ACTION ECONOMY',[top,*resources,status],tone='cyan')
    combined=ui.width>=88 and (ui.height>=28 or not ui.tty)
    if not combined and (ui.height>=40 or not ui.tty) and ui.width>=38:
        lines+=ui.panel('BATTLE STAGE',stage(ui,capture(b),idx),tone='muted')
    grid=arena(b,cursor,preview)[:b.height+1]
    threats=[]
    for i,e in enumerate(b.enemies):
        if not e.alive: continue
        plan=b.plans.get(i,{})
        mark='>' if i==idx else ' '
        name=f'{mark}#{i+1} {safe(e.name)}'
        health=ui.paint(name,'cyan' if i==idx else 'white')+' '+ui.meter(e.hp,e.max_hp,5,'red')
        intent='CANCELLED' if i in b.cancelled else plan.get('name','Waiting')
        intent_text=ui.paint(f'{intent} | DMG {plan.get("damage",0)}','muted' if i in b.cancelled else 'red' if plan.get('kind') in ('strike','charge','trap','siege') else 'gold')
        threats.extend([health+'  /  '+intent_text] if combined else [health,'   '+intent_text])
    if not threats: threats=['No living enemies']
    if combined:
        gw=29; sw=ui.width-gw-2
        left=ui.panel('BATTLE STAGE',stage(ui,capture(b),idx,width=sw),width=sw,tone='muted')
        right=ui.panel('TACTICAL GRID',grid+['@ Hero  ! Danger'],width=gw,tone='cyan')
        lines += [a+'  '+b for a,b in zip(left,right)]
        lines+=ui.panel('ENEMY INTENTS',threats,tone='red')
    elif ui.width>=72: lines+=ui.pair('TACTICAL GRID',grid,'ENEMY INTENTS',threats)
    else: lines+=ui.panel('TACTICAL GRID',grid,tone='cyan')+ui.panel('ENEMY INTENTS',threats,tone='red')
    objective=OBJECTIVE_TEXT[b.objective]
    if b.objective in ('capture','defense','treasure'): objective+=f' | Progress {b.goal_progress} | Relic {b.object_hp}'
    warning='DANGER: #'+', #'.join(danger)+' targeting your tile' if danger else 'Position clear of marked strikes'
    lines+=wrap(ui.paint(objective,'gold')+' | '+ui.paint(warning,'red' if danger else 'green'),ui.width)
    if cursor is None:
        actions=[('1','Attack',r.attack),('2','Skill',min([b.skill_cost(s) for s in h.skills] or [r.skill])),('3','Guard',r.guard),('4','Heavy',r.skill),('5','Item',r.item),('6','Interrupt',r.interrupt),('7','Break',r.attack),('9','Flee',r.ap)]
        labels=[]
        for key,name,cost in actions:
            disabled=b.ap<cost or (key=='3' and b.guarded) or (key=='2' and all(b.skill_reason(s) for s in h.skills))
            labels.append(ui.paint(f'[{key}] {name} {cost}AP','muted' if disabled else 'gold'))
        rows=[]; row=''
        for label in labels:
            if row and cell_width(row+'  '+label)>ui.width-4: rows.append(row);row=''
            row+=('  ' if row else '')+label
        if row: rows.append(row)
        lines+=ui.panel('ACTIONS',rows+['[E] End turn  [F] Focus  [I] Intel  [8] Log  [V] Status',f'[T] Motion {"ON" if Animator(ui).enabled else "OFF"}  |  WASD / Arrows: move'],tone='gold')
    else:
        lines+=ui.panel('TARGETING',wrap(notice,ui.width-4),tone='purple');notice=''
    if ui.height>=43: lines+=ui.panel('COMBAT LOG',cli.log_lines(history,2),tone='muted')
    elif history and not notice: lines+=wrap(ui.paint('LAST: '+safe(history[-1]),'muted'),ui.width)
    if notice: lines+=wrap(ui.paint(safe(notice),'gold'),ui.width)
    ui.screen('Tactical battle',lines,footer or '',subtitle=f'ROUND {b.round:02} / PHASE {b.phase} / {"BOSS" if b.boss else "ENCOUNTER"}')


def choose_cell(b,history,skill=None,action='skill',preferred=None):
    reach=skill.reach if skill else 1 if action in ('heavy','interrupt') else b.player.reach
    valid=lambda q:b.valid_target(q,reach)
    candidates=[e.pos for e in b.living if valid(e.pos)]
    if skill and b.pattern(skill)=='line': candidates=[q for q in candidates if q[0]==b.player.pos[0] or q[1]==b.player.pos[1]]
    if skill and b.pattern(skill)=='burst': candidates=[q for q in candidates if q not in b.walls]
    if action=='break': candidates=[q for q,t in sorted(b.terrain.items()) if t in ('barrel','wall') and valid(q)]
    if preferred is not None and preferred<len(b.enemies) and b.enemies[preferred].pos in candidates: cursor=b.enemies[preferred].pos
    else: cursor=next(iter(candidates),b.player.pos)
    while True:
        target=next((e for e in b.living if e.pos==cursor),None)
        preview=b.skill_cells(skill,cursor) if skill else {cursor}
        target_ok=valid(cursor)
        if action=='break': target_ok=target_ok and b.terrain.get(cursor) in ('barrel','wall')
        elif not skill or b.pattern(skill) in ('line','single','chain'): target_ok=target_ok and target is not None
        if skill and b.pattern(skill)=='burst': target_ok=target_ok and cursor not in b.walls
        if skill and b.pattern(skill)=='line': target_ok=target_ok and (cursor[0]==b.player.pos[0] or cursor[1]==b.player.pos[1])
        name=skill.name if skill else action.upper(); hits=[f'#{i+1} {e.name}' for i,e in enumerate(b.enemies) if e.alive and e.pos in preview]
        notice=f'{name} | {cursor} | Range {reach} | {"IN RANGE" if target_ok else "INVALID TARGET / LOS"} | Area targets: '+(', '.join(hits) or 'none')
        notice+=' | Tiles: '+ ' '.join(f'{x},{y}' for x,y in sorted(preview))
        screen(b,history,notice,cursor,preview,'ARROW / WASD: aim | F: next valid cell | E/Enter: confirm | X: cancel',preferred)
        c=read_key(); c=ALIASES.get(c,c)
        if c in DIRECTIONS:
            q=add(cursor,DIRECTIONS[c]);
            if 0<=q[0]<b.width and 0<=q[1]<b.height: cursor=q
        elif c=='F' and candidates: cursor=candidates[(candidates.index(cursor)+1)%len(candidates)] if cursor in candidates else candidates[0]
        elif c=='X': return None,None,False
        elif c in ('E','ENTER','\r','\n'):
            if target_ok: return target,cursor,True

def skill_menu(b):
    rows=[]; skills=b.hero.skills
    for i,s in enumerate(skills,1):
        rows.extend([f'[{i}] {s.name} | {b.skill_cost(s)} AP | {s.cost} {s.kind} | {b.pattern(s)} | R{s.reach}',f'    {b.skill_reason(s) or "READY"} | {s.description}'])
    if hasattr(b,'combos'):
        for c in b.combos: rows.append(f'Combo {c.id}: {c.setup} -> {c.payoff} | {c.bonus_pct*b.strength/100:g}% bonus | {c.window} rounds | refund {c.refund if b.refunds else 0}')
    cli.UI.screen('Tactical skills',cli.UI.panel('SKILL BOOK',rows),'[X] Cancel')
    c=cli.choose('Skill',{str(i+1) for i in range(len(skills))}|{'X'})
    return None if c=='X' else skills[int(c)-1]

def play(b):
    history=deque(maxlen=300); cli.collect(b,history); notice=''; preferred=None; animator=Animator(cli.UI)
    while b.result=='ongoing':
        screen(b,history,notice,preferred=preferred); c=read_key(); c=ALIASES.get(c,c); notice=''; ok=False
        target=cell=skill=item=None; action=None
        if c in DIRECTIONS: action='move'
        elif c in ('E','ENTER','\r','\n'): action='end'
        elif c in ('1','4','6','7'):
            action={'1':'attack','4':'heavy','6':'interrupt','7':'break'}[c]
            target,cell,confirmed=choose_cell(b,history,action=action,preferred=preferred)
            if not confirmed: continue
        elif c=='2':
            skill=skill_menu(b)
            if skill is None: continue
            action='skill'
            if b.pattern(skill) not in ('self','ring'):
                target,cell,confirmed=choose_cell(b,history,skill,preferred=preferred)
                if not confirmed: continue
        elif c=='3': action='guard'
        elif c=='5':
            item=item_menu(b.hero,b)
            if not item: continue
            action='item'
        elif c=='8': cli.history_screen(history); continue
        elif c=='9':
            if cli.choose('Flee? Y/N',{'Y','N'})!='Y': continue
            action='flee'
        elif c=='V': cli.status(b.hero,b); continue
        elif c=='I': detail_screen(b,history); cli.UI.pause(); continue
        elif c=='F':
            living=[i for i,e in enumerate(b.enemies) if e.alive]
            if living:
                current=focus(b,preferred=preferred)
                preferred=living[(living.index(current)+1)%len(living)] if current in living else living[0]
            continue
        elif c=='T': cli.UI.animation=not cli.UI.animation; notice='Motion '+('enabled' if cli.UI.animation else 'disabled'); continue
        else: continue
        before=capture(b); events=[]; start=None
        def observe(phase,i,plan):
            nonlocal start
            if phase=='before': start=(capture(b),len(b.log))
            elif start is not None:
                events.append((i,dict(plan),start[0],capture(b),tuple(b.log[start[1]:])));start=None
        if action=='end' and animator.enabled: b._presentation_observer=observe
        try:
            if action=='move': ok,notice=b.move(add(b.player.pos,DIRECTIONS[c]))
            else: ok,notice=b.act(action,target,skill,cell=cell,item=item)
        finally:
            if hasattr(b,'_presentation_observer'): del b._presentation_observer
        after=capture(b)
        if ok and animator.enabled:
            if action=='end':
                for i,plan,old,new,logs in events:
                    kind=plan['kind']; label=f'#{i+1} {old.units[i].name} / {plan["name"]}'
                    if any('cancelled' in x.lower() for x in logs) or new.units[i].hp<=0 and old.units[i].hp>0 and not any(' hits ' in x for x in logs): kind='cancel'
                    if kind=='charge' and old.units[i].pos==new.units[i].pos and not any(' hits ' in x or 'attack avoided' in x for x in logs): kind='wait'
                    animator.sequence(old,new,i,i,label,kind,logs)
                if events and events[-1][3]!=after: animator.show(after,focus(b,preferred=preferred),'ROUND TRANSITION',.18,caption='Next round / status resolution')
            else:
                if target is not None: preferred=next((i for i,e in enumerate(b.enemies) if e is target),preferred)
                # Area actions focus an actually affected enemy if no direct target exists.
                changed=[i for i,u in after.units.items() if i!=-1 and i in before.units and u.hp<before.units[i].hp]
                idx=preferred if target is not None and preferred in before.units else changed[0] if changed else focus(b,preferred=preferred)
                if idx is None: idx=next((i for i,u in before.units.items() if i!=-1 and u.hp>0),None)
                kind=action
                if skill:
                    kind='heal' if skill.effect in ('heal','sanctuary') else 'guard' if skill.effect in ('counter','barrier','stealth') else 'skill'
                if item=='bomb': kind='skill'
                label=skill.name if skill else item.upper() if item else action.upper()
                animator.sequence(before,after,-1,idx,label,kind,tuple(b.log))
            if b.result!='ongoing': animator.finish(after,preferred if preferred in after.units else focus(b))
        cli.collect(b,history)
        if notice: history.append(safe(notice))
    return history
