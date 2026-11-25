"""New default terminal frontend. Uses existing panel, class creation and character UI."""
import argparse
from pathlib import Path
from random import Random
from collections import deque
from . import cli
from .ui import Terminal,safe
from .models import MAX_LEVEL
from .keys import read_key
from .grid import DIRECTIONS,add
from .procedural import ProceduralDungeon,Progress,key
from .procedural_save import SAVE,save_run,load_run
from .items import ITEMS,count

ALIASES={'W':'UP','A':'LEFT','S':'DOWN','D':'RIGHT'}
MARKS={'entrance':'E','guardian':'G','enemy':'M','boss':'B','treasure':'T','cache':'I','trap':'!','camp':'C','altar':'A','shop':'$'}
TONES={'@':'cyan','G':'red','M':'red','B':'red','T':'gold','I':'green','!':'red','C':'green','A':'purple','$':'gold','E':'cyan','#':'muted','?':'muted','+':'green','X':'red'}

def paint_map(d,full=False):
    m=d.map; seen=set(d.progress.seen); cleared=set(d.progress.cleared); ui=cli.UI
    # Keep grid columns intact even in a narrow terminal; show a centered viewport.
    ww=min(m.width,ui.width-6); hh=min(m.height,max(7,ui.height-14))
    x0=max(0,min(m.width-ww,d.position[0]-ww//2)); y0=max(0,min(m.height-hh,d.position[1]-hh//2))
    rows=[]
    for y in range(y0,y0+hh):
        row=''
        for x in range(x0,x0+ww):
            p=(x,y); k=key(p)
            if p==d.position: ch='@'
            elif not full and k not in seen: ch='?'
            elif p not in m.tiles: ch='#'
            elif k in cleared: ch='+'
            elif p==m.boss and d.seals<3: ch='X'
            else: ch=MARKS.get(m.features.get(p),'.')
            row+=ui.paint(ch,TONES.get(ch,'white'))
        rows.append(row)
    return rows

def item_menu(h,battle=None,shop=False):
    ui=cli.UI; ids=list(ITEMS); rows=[]
    for i,k in enumerate(ids,1):
        spec=ITEMS[k]; price=max(1,spec.price-h.attrs['CHA']); label=f'{price} gold' if shop else f'x{count(h,k)}'
        rows += [f'[{i}] {spec.name} | {label}', '    '+spec.description+(' (Combat)' if spec.combat_only else '')]
    ui.screen('Merchant' if shop else 'Inventory',ui.panel('ITEMS',rows),'[1-8] Pilih item | [X] Kembali')
    choice=cli.choose('Item',set('12345678X'))
    return None if choice=='X' else ids[int(choice)-1]

def arena_lines(b):
    ui=cli.UI; rows=['   '+' '.join(str(x) for x in range(b.width))]
    positions={e.pos:str(i) for i,e in enumerate(b.living,1)}
    for y in range(b.height):
        cells=[]
        for x in range(b.width):
            p=(x,y); ch='@' if p==b.player.pos else positions.get(p,'#' if p in b.walls else 'C' if p in b.cover else '.')
            cells.append(ui.paint(ch,'cyan' if ch=='@' else 'red' if ch.isdigit() else 'gold' if ch=='C' else 'muted'))
        rows.append(f'{y}  '+' '.join(cells))
    return rows+['@ Hero | 1-4 Enemy | # Wall | C Cover']

def battle_screen(b,history,notice='',disengage=False):
    ui=cli.UI; p=b.player; h=b.hero
    stats=[f'{safe(h.name)} | {h.class_name} Lv {h.level}',*cli.resource_lines(h,p.hp),f'AC {p.armor} | Barrier {p.barrier} | Range {p.reach}',f'Gerak {b.steps_left}/2 | {cli.conditions(p)}']
    enemies=[f'{i} {e.name} HP {e.hp}/{e.max_hp} | R{p.distance(e)} | {cli.conditions(e)}' for i,e in enumerate(b.living,1)]
    lines=ui.pair('HERO',stats,'ENEMIES',enemies)
    if ui.width>=72: lines+=ui.pair('TACTICAL GRID 9 x 7',arena_lines(b),'COMBAT LOG',cli.log_lines(history,5))
    else: lines+=ui.panel('TACTICAL GRID 9 x 7',arena_lines(b))+ui.panel('COMBAT LOG',cli.log_lines(history,3))
    lines+=ui.panel('ACTIONS',['[1] Attack  [2] Skill  [3] Dodge  [4] Disengage','[5] Inventory  [6] Flee  [7] Status  [8] Log'])
    if notice: lines+=ui.panel('NOTICE',[notice])
    ui.screen('Boss battle' if b.boss else 'Grid battle',lines,'ARROW / WASD: move | '+('Disengage aktif: pilih arah atau 4 untuk batal.' if disengage else '2 langkah gratis per turn.'),subtitle=f'ROUND {b.round} / TURN {p.turns}')

def play_battle(b):
    history=deque(maxlen=300); cli.collect(b,history); notice=''; disengage=False
    while b.result=='ongoing':
        battle_screen(b,history,notice,disengage); choice=read_key(); choice=ALIASES.get(choice,choice); notice=''
        if choice in DIRECTIONS:
            dest=add(b.player.pos,DIRECTIONS[choice]); ok,notice=b.act('disengage',dest=dest) if disengage else b.move(dest)
            if ok: disengage=False
        elif choice=='4': disengage=not disengage; continue
        elif choice=='7': cli.status(b.hero,b); continue
        elif choice=='8': cli.history_screen(history); continue
        elif choice=='1':
            target,notice=cli.select_target(b,b.player.reach)
            if target is None: continue
            ok,notice=b.act('attack',target)
        elif choice=='2':
            skill=cli.skill_menu(b)
            if skill is None: continue
            target=None
            if skill.dice[0]:
                target,notice=cli.select_target(b,skill.reach)
                if target is None: continue
            ok,notice=b.act('skill',target,skill)
        elif choice=='5':
            item=item_menu(b.hero,b)
            if item is None: continue
            ok,notice=b.act('item',item=item)
        elif choice=='3': ok,notice=b.act('guard')
        elif choice=='6':
            if cli.choose('Kabur? Y/N',{'Y','N'})=='N': continue
            ok,notice=b.act('flee')
        else: continue
        if choice not in DIRECTIONS and ok: disengage=False
        cli.collect(b,history)
        if notice: history.append(safe(notice))
    return history

def help_screen():
    cli.UI.screen('Guide',cli.UI.panel('PROCEDURAL DUNGEON',[
      'Arrow / WASD: berjalan tanpa Enter di terminal interaktif.', 'E Entrance | G Guardian | M musuh opsional | B Boss | X terkunci.',
      'T Treasure | I Supply | C Camp | A Altar | $ Shop | ! Trap.',
      '? belum terlihat | # dinding | + selesai | @ posisi kamu.', 'Kalahkan 3 guardian sebelum masuk boss. N di boss yang selesai untuk turun.',
      'Treasure, camp, altar, supply: tekan E. Setiap objek hanya sekali.', 'Campaign: 6 AP; practice: 5 AP. Arrow = 1 AP; E = end turn.',
      'Dinding menghalangi line of sight; pilih target dengan cursor dan E.', 'Heavy: dorong musuh. Interrupt: batalkan serangan. Guard: mitigasi.', 'Grid lama: 2 gerak dan 1 aksi, gunakan --grid.',
      'F: focus target | I: detailed intel & terrain legend | T: toggle motion.', 'Checkpoint otomatis sebelum combat dan setelah hasil. Ctrl+C kembali ke checkpoint.' ]))
    cli.UI.pause()

def exploration_screen(d,notice=''):
    ui=cli.UI; h=d.hero; m=d.map
    left=[f'{safe(h.name)} | {h.class_name} Lv {h.level}',*cli.resource_lines(h),f'Gold {h.gold} | Poin {h.points}',f'XP {h.xp}/{h.xp_needed} | Menang {h.wins} / Kalah {h.defeats}']
    right=[f'Floor {h.floor+1}/{d.progress.total} | {m.theme.name}',f'Segel {d.seals}/3 | Boss: {m.theme.boss}',f'Lokasi {d.position} | {d.feature}',f'Peta {m.width} x {m.height} | Seed {d.progress.seed}', 'Boss terbuka' if d.seals==3 else 'Boss masih terkunci']
    lines=ui.pair('ADVENTURER',left,'OBJECTIVE',right)
    maprows=paint_map(d)
    legend=['@ Kamu  # Wall  ? Unknown','G Guardian  M Enemy  B Boss','T Treasure  I Supply  ! Trap','C Camp  A Altar  $ Shop','E Entrance  X Locked  + Done']
    if ui.width>=72: lines+=ui.pair('PETA DUNGEON',maprows,'LEGEND',legend)
    else: lines+=ui.panel('PETA DUNGEON',maprows)+ui.panel('LEGEND',legend)
    lines+=ui.panel('COMMANDS',['[E] Interact  [I] Inventory  [B] Shop  [N] Next floor','[P] Attributes  [V] Status  [H] Guide  [Q] Save & menu'])
    if notice: lines+=ui.panel('NOTICE',[notice])
    ui.screen('Exploration',lines,'ARROW / WASD: move | Auto-save aktif.')

def campaign(d,path):
    notice=''; h=d.hero
    while not h.finished:
        if d.pending:
            b=d.encounter();
            if d.mode=="tactical":
                from .tactical_cli import play
                history=play(b)
            else: history=play_battle(b)
            messages=d.resolve(b); save_run(d,path)
            cli.UI.screen(b.result,cli.UI.panel(b.result.upper(),messages)+cli.UI.panel('COMBAT LOG',cli.log_lines(history,4)))
            cli.UI.pause('Enter untuk lanjut'); notice=' '.join(messages); continue
        exploration_screen(d,notice); choice=read_key(); choice=ALIASES.get(choice,choice); notice=''
        if choice in DIRECTIONS: _,notice=d.move(choice)
        elif choice=='E':
            attr='WIS'
            if d.feature=='altar':
                attr=cli.choose('Atribut WIS / CHA / INT / X',{'WIS','CHA','INT','X'})
                if attr=='X': continue
            _,notice=d.interact(attr)
        elif choice=='I':
            item=item_menu(h)
            if item: _,notice=d.use(item)
        elif choice=='B':
            if d.feature not in ('shop','entrance'): notice='Shop hanya di entrance atau petak $.'
            else:
                item=item_menu(h,shop=True)
                if item: _,notice=d.buy(item)
        elif choice=='P': cli.allocate(h)
        elif choice=='V': cli.status(h)
        elif choice=='H': help_screen()
        elif choice=='N': _,notice=d.advance()
        elif choice=='Q': save_run(d,path); return
        else: continue
        save_run(d,path)
    cli.UI.screen('Campaign complete',cli.UI.panel('VICTORY',[f'{safe(h.name)} menyelesaikan {d.progress.total} lantai!',f'Level {h.level} | Menang {h.wins} | Kalah {h.defeats} | Gold {h.gold}']))
    cli.UI.pause()

def practice(seed=None,level=5):
    from .practice import make_practice
    from .tactical_cli import play
    h=cli.new_hero()
    if h is None: return
    choice=cli.choose('Practice: [1] Mixed squad [2] Boss [3] Random objective [4] Solo [X] Back',{'1','2','3','4','X'})
    if choice=='X': return
    b=make_practice(h,{'1':'mixed','2':'boss','3':'objective','4':'solo'}[choice],seed,level)
    history=play(b)
    cli.UI.screen('Practice result',cli.UI.panel(b.result.upper(),[f'{k}: {v}' for k,v in b.metrics.items()])+cli.UI.panel('COMBAT LOG',cli.log_lines(history,5)))
    cli.UI.pause()

def main():
    parser=argparse.ArgumentParser(description='Dungeon Chronicles: Battle Motion Edition')
    parser.add_argument('--seed',type=int); parser.add_argument('--floors',type=int,default=10,choices=range(5,51),metavar='5..50')
    parser.add_argument('--arena',action='store_true',help='Practice tactical combat without a campaign save'); parser.add_argument('--arena-level',type=int,default=5,choices=range(1,11)); parser.add_argument('--grid',action='store_true',help='Legacy procedural grid battle'); parser.add_argument('--save',type=Path); parser.add_argument('--plain',action='store_true'); parser.add_argument('--ascii',action='store_true'); parser.add_argument('--no-clear',action='store_true')
    parser.add_argument('--no-animation',action='store_true',help='Disable frame animations'); parser.add_argument('--fast-animation',action='store_true',help='Play motion at double speed'); parser.add_argument('--motion-gallery',action='store_true',help='Preview all class animations without a save')
    args=parser.parse_args(); args.save=args.save or (SAVE.with_name('balanced_grid.json') if args.grid else SAVE); cli.UI=Terminal(args.plain,args.no_clear,args.ascii)
    cli.UI.animation=not args.no_animation; cli.UI.animation_speed=.5 if args.fast_animation else 1.0
    try:
        if args.motion_gallery:
            from .motion_gallery import gallery
            gallery(); return
        if args.arena:
            practice(args.seed,args.arena_level); return
        while True:
            summary=['Tidak ada checkpoint.']; d=None
            if args.save.exists():
                try:
                    d=load_run(args.save); summary=[f'{safe(d.hero.name)} / {d.hero.class_name} Lv {d.hero.level}',f'Floor {d.hero.floor+1}/{d.progress.total} | Seed {d.progress.seed}']
                except (ValueError,OSError,KeyError,TypeError,AttributeError) as e: summary=['Checkpoint gagal: '+safe(e)]
            cli.UI.screen('Main menu',cli.UI.panel('PROCEDURAL GRID EDITION' if args.grid else 'BATTLE MOTION EDITION',['       /\\        D U N G E O N', '      /  \\       C H R O N I C L E S', '     / /\\ \\      Chronicle of the Fallen King', '    /_/  \\_\\     B A T T L E   M O T I O N', 'Explore. Collect. Fight. Descend.'])+cli.UI.panel('CHECKPOINT',summary)+cli.UI.panel('MAIN MENU',['[1] Continue','[2] New adventure','[3] Guide','[4] Exit','[5] Practice arena (balanced, 5 AP)','[6] Motion gallery / class showcase']), 'Gunakan angka + Enter pada menu.')
            choice=cli.choose('Pilih',set('123456'))
            if choice=='6':
                from .motion_gallery import gallery
                gallery(); continue
            if choice=='5': practice(args.seed,args.arena_level); continue
            if choice=='4': print('Sampai jumpa, Adventurer.'); return
            if choice=='3': help_screen(); continue
            if choice=='1' and d is None: continue
            if choice=='2':
                if args.save.exists() and cli.choose('Timpa checkpoint procedural? Y/N',{'Y','N'})=='N': continue
                h=cli.new_hero()
                if h is None: continue
                h.inventory={'ether':1,'ration':1}; seed=args.seed if args.seed is not None else Random().getrandbits(63)
                d=ProceduralDungeon(h,Progress(seed,args.floors),mode="grid" if args.grid else "tactical"); save_run(d,args.save)
            campaign(d,args.save)
    except (KeyboardInterrupt,EOFError): print('\nPermainan ditutup. Checkpoint terakhir tetap tersimpan.')
