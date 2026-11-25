"""Stackable consumables, usable in exploration and/or combat."""
from dataclasses import dataclass
@dataclass(frozen=True)
class Item:
    name:str
    price:int
    description:str
    combat_only:bool=False
ITEMS={
 'potion':Item('Health Potion',10,'Pulihkan 14 + level HP.'),
 'greater':Item('Greater Potion',24,'Pulihkan 30 + level HP.'),
 'ether':Item('Ether',13,'Pulihkan 10 MP.'),
 'ration':Item('Ration',11,'Pulihkan 8 stamina.'),
 'antidote':Item('Purifying Tonic',12,'Hapus burn, bleed, poison, corrode, slow.',True),
 'shield':Item('Shield Scroll',18,'Barrier 12 + level.',True),
 'bomb':Item('Fire Bomb',20,'10 damage ke semua musuh dalam jarak 2.',True),
 'elixir':Item('Elixir',38,'Pulihkan 40% HP, MP, dan stamina.'),
}
def count(h,key): return h.potions if key=='potion' else h.inventory.get(key,0)
def grant(h,key,n=1):
    if key=='potion': h.potions+=n
    else: h.inventory[key]=h.inventory.get(key,0)+n

def use_item(h,key,battle=None):
    if key not in ITEMS or count(h,key)<=0: return False,'Item tidak tersedia.'
    item=ITEMS[key]; p=battle.player if battle else h
    if item.combat_only and not battle: return False,'Hanya dapat digunakan saat combat.'
    changed=False
    def heal(obj,attr,limit,amount):
        old=getattr(obj,attr); setattr(obj,attr,min(limit,old+amount)); return getattr(obj,attr)!=old
    if key in ('potion','greater'): changed=heal(p,'hp',h.max_hp,(14 if key=='potion' else 30)+h.level)
    elif key=='ether': changed=heal(h,'mana',h.max_mana,10)
    elif key=='ration': changed=heal(h,'stamina',h.max_stamina,8)
    elif key=='elixir':
        changed=any([heal(p,'hp',h.max_hp,max(1,h.max_hp*2//5)),heal(h,'mana',h.max_mana,max(1,h.max_mana*2//5)),heal(h,'stamina',h.max_stamina,max(1,h.max_stamina*2//5))])
    elif key=='antidote':
        for status in ('burn','bleed','poison','corrode','slow'):
            if p.conditions.pop(status,None) is not None: changed=True
    elif key=='shield':
        value=12+h.level; changed=p.barrier<value; p.barrier=max(p.barrier,value)
    elif key=='bomb':
        targets=[e for e in battle.living if p.distance(e)<=2]; changed=bool(targets)
        for e in targets: battle._damage(e,10)
    if not changed: return False,'Item tidak memberikan efek saat ini.'
    grant(h,key,-1)
    if battle: h.hp=p.hp
    return True,f'{item.name} digunakan.'
