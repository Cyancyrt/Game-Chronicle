"""Persistent character state, distinct from temporary combat state."""
from dataclasses import dataclass, field
from .content import CLASSES, ATTRIBUTES

MAX_LEVEL = 10


@dataclass
class Hero:
    name: str
    class_name: str
    level: int = 1
    xp: int = 0
    points: int = 0
    attrs: dict = field(default_factory=lambda: dict.fromkeys(ATTRIBUTES, 0))
    hp: int = 0
    mana: int = 0
    stamina: int = 0
    gold: int = 15
    potions: int = 2
    floor: int = 0
    room: str = "E"
    cleared: list = field(default_factory=list)
    visited: list = field(default_factory=lambda: ["E"])
    rested: bool = False
    finished: bool = False
    wins: int = 0
    defeats: int = 0
    inventory: dict = field(default_factory=dict)

    @classmethod
    def create(cls, name, class_name):
        hero = cls(name.strip()[:30] or "Adventurer", class_name)
        hero.restore()
        return hero

    @property
    def spec(self):
        return CLASSES[self.class_name]

    @property
    def max_hp(self):
        return self.spec.hp + (self.level - 1) * 7 + self.attrs["CON"] * 4

    @property
    def max_mana(self):
        return self.spec.mana + (self.level - 1) * 2 + self.attrs["INT"] * 2 + self.attrs["WIS"] * 2

    @property
    def max_stamina(self):
        return self.spec.stamina + (self.level - 1) + self.attrs["CON"]

    @property
    def ac(self):
        return min(19, self.spec.ac + (self.level - 1) // 3 + self.attrs["DEX"] // 2)

    @property
    def attack(self):
        return min(11, self.spec.attack + (self.level - 1) // 2)

    @property
    def bonus_damage(self):
        main = {"Mage": "INT", "Cleric": "WIS", "Rogue": "DEX", "Archer": "DEX"}.get(self.class_name, "STR")
        return 2 + (self.level - 1) // 2 + self.attrs[main]

    @property
    def xp_needed(self):
        return 40 + self.level * 10

    @property
    def skills(self):
        return [s for s in self.spec.skills if s.level <= self.level]

    def restore(self):
        self.hp, self.mana, self.stamina = self.max_hp, self.max_mana, self.max_stamina

    def recover(self):
        self.hp = min(self.max_hp, self.hp + max(4, self.max_hp // 4))
        self.mana = min(self.max_mana, self.mana + 5)
        self.stamina = min(self.max_stamina, self.stamina + 5)

    def gain_xp(self, amount):
        messages = []
        self.xp += amount
        while self.level < MAX_LEVEL and self.xp >= self.xp_needed:
            self.xp -= self.xp_needed
            self.level += 1
            self.points += 2
            self.restore()
            messages.append(f"LEVEL UP! Level {self.level}; +2 poin atribut.")
            messages.extend(f"Skill baru: {s.name}" for s in self.skills if s.level == self.level)
        if self.level == MAX_LEVEL:
            self.xp = min(self.xp, self.xp_needed - 1)
        return messages

    def allocate(self, attr):
        if attr not in self.attrs or self.points <= 0 or self.attrs[attr] >= 5:
            return False
        old_hp, old_mp, old_st = self.max_hp, self.max_mana, self.max_stamina
        self.attrs[attr] += 1
        self.points -= 1
        self.hp += self.max_hp - old_hp
        self.mana += self.max_mana - old_mp
        self.stamina += self.max_stamina - old_st
        return True
