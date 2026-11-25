"""Dungeon Chronicles terminal frontend; gameplay remains in models/combat/world."""
import argparse
from collections import deque
from pathlib import Path
from random import Random
from .content import CLASSES, ATTRIBUTES, FLOORS
from .models import Hero, MAX_LEVEL
from .world import Dungeon, ROOMS
from .storage import SAVE, save, load, import_legacy
from .ui import Terminal, safe, cell_width, wrap
from .sprites import HEROES


UI = Terminal()


def choose(prompt, choices):
    return UI.ask(prompt, choices)


def bar(current, maximum, size=12, tone='green'):
    return UI.meter(current, maximum, size, tone)


def resource_lines(hero, hp=None):
    hp = hero.hp if hp is None else hp
    return ['HP  ' + bar(hp, hero.max_hp, tone='red' if hp*3 <= hero.max_hp else 'green'),
            'MP  ' + bar(hero.mana, hero.max_mana, tone='blue'),
            'ST  ' + bar(hero.stamina, hero.max_stamina, tone='gold')]


def status(hero, battle=None):
    hp = battle.player.hp if battle else hero.hp
    ac = battle.player.armor if battle else hero.ac
    left = [f'{safe(hero.name)} / {hero.class_name} / Lv {hero.level}', hero.spec.role,
            *resource_lines(hero, hp), 'XP  ' + (bar(hero.xp, hero.xp_needed, tone='purple') if hero.level < MAX_LEVEL else 'MAX LEVEL'),
            f'AC {ac} | ATK +{hero.attack} | 1d{hero.spec.weapon}+{hero.bonus_damage} DMG',
            f'Gold {hero.gold} | Potion {hero.potions}']
    right = [f'Poin tersedia: {hero.points}', ' | '.join(f'{k} +{v}' for k,v in hero.attrs.items()),
             f'Menang {hero.wins} | Kalah {hero.defeats}', '', UI.paint(hero.spec.passive, 'gold'), hero.spec.passive_desc]
    skills=[]
    for s in hero.spec.skills:
        unlocked = s in hero.skills
        state = UI.paint('TERBUKA', 'green') if unlocked else UI.paint(f'LOCK Lv {s.level}', 'muted')
        skills += [f'{s.name} / {state} / {s.cost} {s.kind} / CD {s.cooldown}',
                   '  ' + (f'{s.pattern} | Range {s.reach} | {s.ap_cost} AP | ' if hasattr(s,'ap_cost') else f'{s.dice[0]}d{s.dice[1]} | Range {s.reach} | ' if s.dice[0] else 'Self | ') + s.description]
    UI.screen('Karakter', UI.pair('PROFIL', left, 'ATRIBUT & PASIF', right) + UI.panel('SKILL BOOK', skills))
    UI.pause()


def allocate(hero):
    notice = ''
    while True:
        lines = [f'Poin tersedia: {hero.points}', 'Maksimum +5 per atribut.', '']
        for k, desc in ATTRIBUTES.items():
            lines.append(f'[{k}] ' + bar(hero.attrs[k], 5, 5, 'cyan') + '  ' + desc)
        if notice: lines += ['', UI.paint(notice, 'gold')]
        UI.screen('Atribut', UI.panel('DISTRIBUSI POIN', lines), '[X] Kembali ke dungeon')
        if not hero.points:
            UI.pause(); return
        attr = choose('Atribut', set(ATTRIBUTES) | {'X'})
        if attr == 'X': return
        notice = f'{attr} meningkat.' if hero.allocate(attr) else 'Atribut telah mencapai batas.'


def new_hero():
    UI.screen('Karakter baru', UI.panel('IDENTITAS', ['Petualangan baru menanti di bawah reruntuhan.', 'Masukkan nama adventurer atau X untuk batal.']))
    name = input('> Nama adventurer: ').strip()
    if name.upper() == 'X': return None
    name = safe(name)[:30]
    keys = list(CLASSES)
    while True:
        rows = []
        for i,(key,spec) in enumerate(CLASSES.items(),1):
            rows += [UI.paint(f'[{i}] {key:<11}', 'gold') + f'  {spec.role}',
                     f'    HP {spec.hp} | AC {spec.ac} | MP {spec.mana} | ST {spec.stamina} | Range {spec.reach}']
        UI.screen('Pilih class', UI.panel('TUJUH JALAN PETUALANG', rows), '[1-7] Lihat detail class  |  [X] Batal', subtitle=f'Adventurer: {name or "Adventurer"}')
        choice = choose('Class', set('1234567X'))
        if choice == 'X': return None
        key = keys[int(choice)-1]; spec = CLASSES[key]
        preview = [*[UI.paint(row, HEROES[key].tone) for row in HEROES[key].idle], f'{key.upper()} / {spec.role}', f'HP {spec.hp} | MP {spec.mana} | ST {spec.stamina}',
                   f'AC {spec.ac} | ATK +{spec.attack} | Damage 1d{spec.weapon} | Range {spec.reach}', '',
                   UI.paint(spec.passive, 'gold'), spec.passive_desc, '', 'SKILL']
        for s in spec.skills:
            preview += [f'Lv {s.level}  {s.name}  ({s.cost} {s.kind}, CD {s.cooldown})', '  '+s.description]
        UI.screen('Konfirmasi class', UI.panel('CLASS PREVIEW', preview), '[Y] Mulai petualangan  |  [N] Pilih ulang  |  [X] Batal')
        answer = choose('Konfirmasi', {'Y','N','X'})
        if answer == 'Y': return Hero.create(name, key)
        if answer == 'X': return None


def conditions(unit):
    return ', '.join(f'{k}({v})' for k,v in unit.conditions.items()) or '-'


def battlefield(battle, width=None):
    # Five equal-width cells; stack the occupants of the same zone instead of overflowing.
    p = battle.player
    cells = []
    for pos in range(5):
        marks = (['P'] if p.pos == pos else []) + [f'M{i}' for i,e in enumerate(battle.living,1) if e.pos == pos]
        cells.append([f'Z{pos}' + (' C' if pos in battle.cover else ''), *marks])
    height = max(map(len, cells))
    w = max(3, min(12, ((width or UI.width)-9)//5))
    result = []
    for i in range(height):
        parts = []
        for cell in cells:
            value = cell[i] if i < len(cell) else ''
            value = value.center(w)
            parts.append(UI.paint(value, 'cyan' if value.strip() == 'P' else 'red' if value.strip().startswith('M') else 'muted'))
        result.append('|'.join(parts))
    return [*result, 'P: Kamu | M: Musuh | C: Cover']


def log_lines(history, count=4):
    result=[]
    for entry in list(history)[-count:]:
        lower = entry.lower()
        tone = 'red' if 'tumbang' in lower or 'opportunity' in lower else 'gold' if 'crit' in lower or 'level up' in lower else 'muted' if 'miss' in lower else 'white'
        result.append(UI.paint('> '+entry, tone))
    return result or ['Belum ada aktivitas.']


def combat_screen(battle, history=(), notice=''):
    p,h = battle.player,battle.hero
    move = not battle.moved and 'slow' not in p.conditions
    left = [f'{safe(p.name)} / {h.class_name} Lv {h.level}', *resource_lines(h, p.hp),
            f'AC {p.armor} | Barrier {p.barrier} | Range {p.reach}',
            'Efek: '+conditions(p), 'Gerak: '+ ('SIAP' if move else 'HABIS / TERHALANG')]
    right=[]
    for i,e in enumerate(battle.living,1):
        right += [UI.paint(f'M{i} {e.name}', 'red'), 'HP  '+bar(e.hp,e.max_hp,10,'red'),
                  f'AC {e.armor} | Jarak {p.distance(e)} | Efek: {conditions(e)}',
                  'Next: '+UI.paint(battle.intent(e),'gold')]
    if not right: right=['Tidak ada musuh tersisa.']
    action = [('1','Basic attack'),('2','Skill book'),('3','Dodge (+2 ST)'),('4','Move (gratis)' if move else 'Move (tidak siap)'),
              ('5','Disengage'),('6',f'Potion ({h.potions})'),('7','Flee'),('8','Info karakter'),('9','Riwayat pertarungan')]
    # Preserve detailed log in a dedicated screen; show latest events on the HUD.
    count = 2 if UI.height <= 27 else 3 if UI.height < 35 else 5
    lines = UI.pair('ADVENTURER',left,'MUSUH',right)
    if UI.width >= 72:
        lines += UI.pair('MEDAN TEMPUR',battlefield(battle,(UI.width-2)//2),'COMBAT LOG',log_lines(history,count))
    else:
        lines += UI.panel('MEDAN TEMPUR',battlefield(battle),tone='cyan') + UI.panel('COMBAT LOG',log_lines(history,count),tone='muted')
    if notice: lines += [UI.paint(wrap(notice, UI.width)[0], 'gold')] if cell_width(notice)<=UI.width else wrap(notice,UI.width)
    lines += UI.panel('AKSI',UI.options(action,columns=3))
    UI.screen('Boss encounter' if battle.boss else 'Combat',lines,'[1-9] Pilih aksi | Gerak maks. 2 zona | Cover: +2 AC dari jarak 2+',
              subtitle=f'ROUND {battle.round:02}  /  TURN {p.turns:02}  /  GILIRANMU')


def collect(battle, history):
    history.extend(safe(line) for line in battle.log)
    battle.log.clear()


def select_target(battle, reach):
    eligible = {str(i):e for i,e in enumerate(battle.living,1) if battle.player.distance(e)<=reach}
    if not eligible: return None, 'Tidak ada target dalam jangkauan. Dekati musuh.'
    if len(eligible)==1: return next(iter(eligible.values())), ''
    lines = [f'[{i}] {e.name} | HP {e.hp}/{e.max_hp} | Jarak {battle.player.distance(e)}' for i,e in eligible.items()]
    UI.screen('Target',UI.panel(f'TARGET DALAM RANGE {reach}',lines),'[X] Batal')
    target = eligible.get(choose('Target',set(eligible)|{'X'}))
    return target, ''


def skill_menu(battle):
    skills = battle.hero.skills
    lines=[]
    for i,s in enumerate(skills,1):
        reason = battle.skill_reason(s)
        if not reason and s.dice[0] and not any(battle.player.distance(e)<=s.reach for e in battle.living): reason='Target di luar range.'
        state=UI.paint(reason,'red') if reason else UI.paint('SIAP','green')
        lines += [f'[{i}] {s.name} | {state}', f'    {s.cost} {s.kind} | CD {s.cooldown} | '+(f'Range {s.reach}' if s.dice[0] else 'Self'), '    '+s.description]
    UI.screen('Skill',UI.panel('KEMAMPUAN AKTIF',lines),'[X] Batal')
    key=choose('Skill',{str(i) for i in range(1,len(skills)+1)}|{'X'})
    if key=='X': return None
    return skills[int(key)-1]


def history_screen(history):
    entries=list(history)
    pages=[entries[i:i+12] for i in range(0,len(entries),12)] or [[]]
    page=len(pages)-1
    while True:
        UI.screen('Combat journal',UI.panel(f'HALAMAN {page+1}/{len(pages)}',log_lines(pages[page],12)), '[P] Sebelumnya | [N] Berikutnya | [X] Kembali')
        key=choose('Perintah',{'P','N','X'})
        if key=='X': return
        page=max(0,min(len(pages)-1,page+(-1 if key=='P' else 1)))


def play_battle(battle):
    history=deque(maxlen=300); collect(battle,history)
    notice=''
    while battle.result=='ongoing':
        combat_screen(battle,history,notice); notice=''
        choice=choose('Aksi',set('123456789'))
        if choice=='8': status(battle.hero,battle); continue
        if choice=='9': history_screen(history); continue
        if choice in ('4','5'):
            p=battle.player
            lines=battlefield(battle)+['',f'Posisi saat ini: Z{p.pos}. Pilih zona berjarak 1-2.',
                                     'Disengage memakai aksi.' if choice=='5' else 'Move gratis, berisiko opportunity attack.']
            UI.screen('Pergerakan',UI.panel('PILIH ZONA',lines),'[0-4] Zona | [X] Batal')
            dest=choose('Zona',set('01234X'))
            if dest=='X': continue
            ok,msg=battle.move(int(dest)) if choice=='4' else battle.act('disengage',dest=int(dest))
        elif choice=='1':
            target,notice=select_target(battle,battle.player.reach)
            if target is None: continue
            ok,msg=battle.act('attack',target)
        elif choice=='2':
            skill=skill_menu(battle)
            if skill is None: continue
            notice=battle.skill_reason(skill)
            if notice: continue
            target=None
            if skill.dice[0]:
                target,notice=select_target(battle,skill.reach)
                if target is None: continue
            ok,msg=battle.act('skill',target,skill)
        else:
            if choice=='7':
                UI.screen('Flee',UI.panel('MUNDUR DARI PERTARUNGAN',['Mencoba kabur dari encounter. Jika gagal, giliran tetap berjalan.']),'[Y] Coba kabur | [N] Kembali')
                if choose('Konfirmasi',{'Y','N'})=='N': continue
            ok,msg=battle.act({'3':'guard','6':'potion','7':'flee'}[choice])
        collect(battle,history)
        if msg:
            notice=msg
            if ok: history.append(safe(msg))
    return list(history)


def help_screen():
    pages=[('EKSPLORASI', ['Tujuan: jelajahi lima lantai dan kalahkan Giant Skeleton.', 'A, B, C: kalahkan monster untuk membuka Gerbang G.', 'Altar T dan Camp R opsional. Camp memulihkan penuh sekali per lantai.', 'Potion dapat dibeli di entrance/camp.', 'Level 3, 5 dan 7 membuka skill baru.', 'Auto-save pada checkpoint di luar pertempuran.', 'Ctrl+C saat combat kembali ke checkpoint terakhir saat dilanjutkan.']),
           ('PERTARUNGAN', ['Gerak gratis maksimum 2 zona, lalu satu aksi. Gunakan jarak dan cover.', 'Serangan: d20 + Attack vs Armor Class. Natural 1 gagal; 20 kritikal (dice damage ganda).', 'Advantage/Disadvantage: lempar 2d20 dan pakai nilai tertinggi/terendah; keduanya saling meniadakan.', 'Dodge membuat lawan disadvantage dan memulihkan 2 stamina.', 'Disengage memakai aksi tetapi mencegah Opportunity Attack saat menjauh.', 'Skill mengonsumsi MP atau stamina sekali; CD adalah jumlah giliran berikutnya yang harus dilewati.']),
           ('EFEK & PROGRES', ['Burn/Bleed: damage di awal turn; Slow: tidak bisa bergerak; Stun: melewatkan turn.', 'Poison: disadvantage; Corrode: -2 AC; Barrier: menyerap damage.', 'Lantai 3+ punya encounter lebih dari satu musuh.', 'Menang memberi XP, gold dan pemulihan.', 'Kalah mengembalikanmu ke entrance; segel selesai tetap tersimpan.'])]
    page=0
    while True:
        name,lines=pages[page]
        UI.screen('Panduan',UI.panel(f'{name} / {page+1}/{len(pages)}',lines),'[P] Sebelumnya | [N] Berikutnya | [X] Kembali')
        key=choose('Perintah',{'P','N','X'})
        if key=='X': return
        page=max(0,min(len(pages)-1,page+(-1 if key=='P' else 1)))


def dungeon_map(dungeon):
    h=dungeon.hero
    def mark(room):
        flag='*' if room==h.room else '#' if room=='G' and not dungeon.unlocked else '+' if room in h.cleared else '.' if room in h.visited else '?'
        return UI.paint(f'[{room}{flag}]', {'*':'cyan','#':'red','+':'green','.':'white','?':'muted'}[flag])
    a,b,c,t,r,g,e=(mark(k) for k in 'ABCTRGE')
    return [f'{t}--{a}-------+', '       |         |', f'      {e}      {c}--{g}', '       |         |',f'{r}--{b}-------+',
            '* Kamu  + Selesai  # Terkunci', '? Baru  . Dikunjungi']


def campaign_screen(dungeon, notice=''):
    h=dungeon.hero; floor=dungeon.floor
    left=[f'{safe(h.name)} / {h.class_name} Lv {h.level}',*resource_lines(h), f'Gold {h.gold} | Potion {h.potions} | Poin {h.points}',
          'XP  '+(bar(h.xp,h.xp_needed,tone='purple') if h.level<MAX_LEVEL else 'MAX LEVEL')]
    right=[f'Lokasi: {dungeon.room_name(h.room)}',f'Boss: {floor.boss} | Rekomendasi Lv {floor.recommended}',
           'Segel  '+bar(sum(k in h.cleared for k in 'ABC'),3,3,'cyan'),
           'Cover: '+', '.join(f'Z{p}' for p in floor.cover), floor.lore]
    lines=UI.pair('ADVENTURER',left,'OBJECTIVE',right)
    destinations=[]
    for k in ROOMS[h.room][1]:
        suffix=' [TERKUNCI]' if k=='G' and not dungeon.unlocked else ' [SELESAI]' if k in h.cleared else ''
        destinations.append((k,dungeon.room_name(k)+suffix))
    if UI.width >= 72:
        lines+=UI.pair('PETA DUNGEON',dungeon_map(dungeon),'TUJUAN TERHUBUNG',UI.options(destinations,two=False))
    else:
        lines+=UI.panel('PETA DUNGEON',dungeon_map(dungeon),tone='cyan')+UI.panel('TUJUAN TERHUBUNG',UI.options(destinations))
    actions=[('S','Status karakter'),('P','Atribut'),('I','Gunakan potion'),('H','Panduan'),('Q','Simpan & menu')]
    if h.room in ('E','R'): actions.append(('BUY',f'Beli potion ({dungeon.potion_price} gold)'))
    if h.room=='R': actions.append(('REST','Camp'+(' (sudah dipakai)' if h.rested else ' (siap)')))
    if h.room=='T': actions.append(('ALTAR','Uji atribut'+(' (selesai)' if 'T' in h.cleared else '')))
    if h.room=='G' and 'G' in h.cleared: actions.append(('N','Turun ke lantai berikutnya'))
    if notice: lines+=wrap('Catatan: '+notice,UI.width)
    lines+=UI.panel('PERINTAH',UI.options(actions,columns=3))
    UI.screen('Eksplorasi',lines,'Checkpoint otomatis tersimpan setelah aksi eksplorasi.',subtitle=f'FLOOR {h.floor+1:02}/{len(FLOORS):02}  /  {floor.name.upper()}')
    return {k for k,_ in destinations+actions}


def campaign(hero, rng, path):
    dungeon=Dungeon(hero,rng); notice=''
    while True:
        if dungeon.pending:
            battle=dungeon.encounter(); history=play_battle(battle)
            messages=dungeon.resolve(battle); save(hero,path)
            title={'victory':'VICTORY','defeat':'DEFEAT','fled':'ESCAPED'}[battle.result]
            UI.screen(title,UI.panel(title,[*messages,'',*resource_lines(hero)],tone='green' if battle.result=='victory' else 'gold')+UI.panel('AKHIR PERTARUNGAN',log_lines(history,6),tone='muted'),'Checkpoint tersimpan.')
            UI.pause('Enter untuk melanjutkan'); notice=' '.join(messages)
        if hero.finished:
            UI.screen('Campaign complete',UI.panel('CAMPAIGN COMPLETE',['Selamat, '+safe(hero.name)+'!', 'Giant Skeleton dikalahkan.',f'{hero.class_name} Lv {hero.level} | Menang {hero.wins} | Kalah {hero.defeats}',f'Gold {hero.gold} | Potion {hero.potions}'],tone='green'),'[Q] Kembali ke menu')
            choose('Perintah',{'Q'}); return
        options=campaign_screen(dungeon,notice); notice=''
        option=choose('Perintah',options)
        if option in ROOMS[hero.room][1]: _,notice=dungeon.move(option)
        elif option=='S': status(hero)
        elif option=='P': allocate(hero)
        elif option=='I': notice='Potion digunakan.' if dungeon.use_potion() else 'Potion tidak dapat digunakan.'
        elif option=='BUY': notice='Potion dibeli.' if dungeon.buy_potion() else 'Gold tidak cukup.'
        elif option=='REST': notice='Seluruh resource pulih.' if dungeon.rest() else 'Camp telah digunakan.'
        elif option=='ALTAR':
            UI.screen('Altar',UI.panel('UJI ATRIBUT',['[WIS] Wisdom','[CHA] Charisma','[INT] Intelligence','Skill check DC 11.']),'[X] Batal')
            attr=choose('Atribut',{'WIS','CHA','INT','X'})
            if attr!='X': notice=dungeon.altar(attr)[1]
        elif option=='N': dungeon.advance(); notice='Memasuki lantai berikutnya.'
        elif option=='H': help_screen()
        elif option=='Q': save(hero,path); return
        save(hero,path)


def main():
    global UI
    parser=argparse.ArgumentParser(description='Dungeon Chronicles - terminal RPG')
    parser.add_argument('--save',type=Path,default=SAVE,help='Lokasi save alternatif.')
    parser.add_argument('--seed',type=int,help='Seed dadu untuk pengujian.')
    parser.add_argument('--import-legacy',type=Path,help='Impor player_save.json versi lama.')
    parser.add_argument('--plain',action='store_true',help='ASCII, tanpa warna dan tanpa clear screen.')
    parser.add_argument('--ascii',action='store_true',help='Gunakan bingkai ASCII untuk terminal lama.')
    parser.add_argument('--no-clear',action='store_true',help='Jangan hapus layar; pertahankan scrollback.')
    args=parser.parse_args(); UI=Terminal(args.plain,args.no_clear,args.ascii); rng=Random(args.seed)
    notice=''
    try:
        if args.import_legacy:
            if args.save.exists() and choose('Timpa save aktif? Y/N',{'Y','N'})=='N': return
            try: save(import_legacy(args.import_legacy),args.save); notice='Save lama diimpor. Statistik disesuaikan dengan engine baru.'
            except (OSError,ValueError,TypeError,KeyError) as error: print('Impor gagal: '+safe(error)); return
        while True:
            summary=['Belum ada checkpoint. Mulai petualangan baru.']; available=False
            if args.save.exists():
                try:
                    h=load(args.save); available=True
                    summary=[f'{safe(h.name)} / {h.class_name} Lv {h.level}',f'Floor {h.floor+1}/{len(FLOORS)} - {FLOORS[h.floor].name}', f'Menang {h.wins} | Kalah {h.defeats} | Gold {h.gold}']
                except (OSError,ValueError,TypeError,KeyError) as error: summary=['Checkpoint tidak dapat dimuat. '+safe(error)]
            logo=['            /\\', '           /  \\', '          | /\\ |', '          | || |', '          | || |', '       ___|_||_|___', '          /____\\', '            ||', '            \\/', '', 'D U N G E O N   C H R O N I C L E S', 'Chronicle of the Fallen King', 'TURN-BASED DUNGEON RPG']
            logo=[UI.paint(x[7:].ljust(13).center(max(26,UI.width-4)) if i<9 else x.center(max(26,UI.width-4)),'gold') for i,x in enumerate(logo)] if UI.width>=42 else ['DUNGEON CHRONICLES','TURN-BASED RPG']
            lines=UI.panel('',logo)+UI.panel('CHECKPOINT',summary,tone='cyan')+UI.panel('MAIN MENU',UI.options([('1','Lanjutkan' if available else 'Lanjutkan (tidak tersedia)'),('2','Karakter baru'),('3','Panduan'),('4','Keluar')]))
            if notice: lines+=UI.panel('INFORMASI',[notice],tone='muted')
            UI.screen('Main menu',lines,'Python terminal edition  /  Ketik angka lalu Enter.'); notice=''
            command=choose('Pilih',set('1234'))
            if command=='4': print('Sampai jumpa, Adventurer.'); return
            if command=='3': help_screen(); continue
            if command=='2':
                if args.save.exists() and choose('Timpa karakter sebelumnya? Y/N',{'Y','N'})=='N': continue
                hero=new_hero()
                if hero is None: continue
                save(hero,args.save)
            else:
                try: hero=load(args.save)
                except (OSError,ValueError,TypeError,KeyError) as error: notice='Save tidak dapat dimuat: '+safe(error); continue
            campaign(hero,rng,args.save)
    except (KeyboardInterrupt,EOFError): print('\nPermainan ditutup. Checkpoint terakhir tetap tersedia jika sudah disimpan.')
