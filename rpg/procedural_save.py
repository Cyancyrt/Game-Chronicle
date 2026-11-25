"""Separate atomic save format; classic checkpoints remain untouched."""
import json,os
from pathlib import Path
from dataclasses import asdict
from .models import Hero,MAX_LEVEL
from .content import CLASSES,ATTRIBUTES
from .items import ITEMS
from .procedural import Progress,ProceduralDungeon,generate,coord,key,GENERATOR_VERSION
SAVE=Path(__file__).resolve().parent.parent/'saves'/'balanced_tactical.json'

def save_run(dungeon,path=SAVE):
    if dungeon.active_battle is not None: raise ValueError('Save hanya di checkpoint luar battle.')
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        json.dump({'version':3,'generator':GENERATOR_VERSION,'hero':asdict(dungeon.hero),'progress':asdict(dungeon.progress),'mode':dungeon.mode},f,indent=2,ensure_ascii=False); f.flush(); os.fsync(f.fileno())
    tmp.replace(path)

def load_run(path=SAVE):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('version')!=3 or data.get('generator')!=GENERATOR_VERSION: raise ValueError('Save bukan versi procedural yang didukung.')
    h=Hero(**data['hero']); p=Progress(**data['progress'])
    if type(p.seed) is not int or type(p.total) is not int or not 5<=p.total<=50 or type(h.floor) is not int or not 0<=h.floor<p.total: raise ValueError('Seed/lantai tidak valid.')
    if h.class_name not in CLASSES or not isinstance(h.name,str) or not h.name.strip() or type(h.level) is not int or not 1<=h.level<=MAX_LEVEL: raise ValueError('Hero tidak valid.')
    if set(h.attrs)!=set(ATTRIBUTES) or any(type(v) is not int or not 0<=v<=5 for v in h.attrs.values()): raise ValueError('Atribut tidak valid.')
    if any(type(v) is not int or v<0 for v in (h.gold,h.potions,h.xp,h.points,h.wins,h.defeats)) or not 1<=h.hp<=h.max_hp or not 0<=h.mana<=h.max_mana or not 0<=h.stamina<=h.max_stamina: raise ValueError('Resource tidak valid.')
    if not isinstance(h.inventory,dict) or any(k not in ITEMS or k=='potion' or type(v) is not int or v<0 for k,v in h.inventory.items()): raise ValueError('Inventory tidak valid.')
    m=generate(p.seed,h.floor,p.total)
    if coord(p.position) not in m.tiles or not set(p.cleared)<={key(q) for q in m.features} or not set(p.seen)<={key((x,y)) for x in range(m.width) for y in range(m.height)} or any(k not in {key(q) for q in m.encounters} or type(v) is not int or v<0 for k,v in p.attempts.items()): raise ValueError('Progress peta tidak valid.')
    if h.finished!=(h.floor==p.total-1 and key(m.boss) in p.cleared): raise ValueError('Status campaign tidak valid.')
    return ProceduralDungeon(h,p,mode=data.get('mode','grid'))
