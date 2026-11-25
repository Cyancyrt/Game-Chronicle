"""Playable level-5 reference arena; no ML or research dependencies."""
from random import Random
from .content import MONSTERS
from .tactical import TacticalBattle, Rules, OBJECTIVES
from .grid import distance

# hp multiplier, telegraph damage multiplier, intent radius, reinforced
PROFILES = {
    'solo': (1.0, 1.0, 0, True),
    'mixed': (1.0, 1.5, 1, False),
    'objective': (1.25, 1.25, 0, False),
    'boss': (1.25, 1.5, 1, True),
}

class PracticeBattle(TacticalBattle):
    def __init__(self, *args, hp_scale, intent_radius, **kwargs):
        self.hp_scale = hp_scale
        self.intent_radius = intent_radius
        super().__init__(*args, **kwargs)
    def _scale_hp(self, e):
        e.max_hp = max(1, round(e.max_hp * self.hp_scale))
        e.hp = e.max_hp
    def _setup_positions(self):
        for e in self.enemies: self._scale_hp(e)
        super()._setup_positions()
    def _spawn(self):
        n = len(self.enemies)
        super()._spawn()
        for e in self.enemies[n:]: self._scale_hp(e)
    def _plan(self, e):
        p = super()._plan(e)
        radius = self.intent_radius
        if radius and p['kind'] in ('strike','trap','charge') and p['cells']:
            base = p['cells']
            p['cells'] = sorted({(x,y) for y in range(self.height) for x in range(self.width)
                if (x,y) not in self.walls and self.los(e.pos,(x,y))
                and any(distance((x,y),q) <= radius for q in base)} | set(base))
        return p

def make_practice(hero, scenario, seed=None, level=5):
    if seed is None: seed = Random().getrandbits(63)
    setup = Random(seed)
    hero.level = level
    hero.restore()
    hero.potions = 1
    hero.inventory = {'ether':1, 'ration':1}
    names = ['Skeleton'] if scenario == 'solo' else ['Goblin Warrior','Goblin Archer','Skeleton Armor'] if scenario == 'mixed' else ['Goblin Captain'] if scenario == 'boss' else setup.sample(list(MONSTERS),3)
    objective = setup.choice(OBJECTIVES) if scenario == 'objective' else 'elimination'
    hp, dmg, radius, reinforced = PROFILES[scenario]
    if reinforced:
        if scenario == 'solo': names = ['Giant Skeleton']
        else: names.append('Goblin Archer' if scenario == 'boss' else 'Medium Slime')
    return PracticeBattle(hero, names, max(1,level//2), boss=scenario=='boss', rng=Random(seed), objective=objective,
                          rules=Rules(ap=5,enemy_damage_scale=dmg),hp_scale=hp,intent_radius=radius)
