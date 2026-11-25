"""Deterministic with a supplied RNG; all temporary state belongs to a battle."""
from dataclasses import dataclass, field
from random import Random
from .content import MONSTERS, Skill
from .models import Hero


def roll(rng, count, sides):
    return sum(rng.randint(1, sides) for _ in range(count))


@dataclass
class Unit:
    name: str
    hp: int
    max_hp: int
    ac: int
    attack: int
    damage: int
    die: int
    dex: int
    reach: int
    pos: int
    ability: str = ""
    effect: str = ""
    conditions: dict = field(default_factory=dict)
    barrier: int = 0
    turns: int = 0
    reaction: bool = True

    @property
    def alive(self):
        return self.hp > 0

    @property
    def armor(self):
        return max(8, min(22, self.ac + 2 * ("guard" in self.conditions)
                         + ("reflex" in self.conditions) - 2 * ("corrode" in self.conditions)
                         - 2 * ("reckless" in self.conditions)))

    def distance(self, other):
        return (abs(self.pos[0]-other.pos[0])+abs(self.pos[1]-other.pos[1])
                if isinstance(self.pos, tuple) else abs(self.pos - other.pos))


class Battle:
    """One action, one movement (up to two zones), one reaction per turn."""
    def __init__(self, hero: Hero, names, tier, boss=False, rng=None, cover=(3,)):
        self.hero = hero
        self.rng = rng or Random()
        self.log = []
        self.round = 1
        self.cooldowns = {}
        self.result = "ongoing"
        self.moved = False
        self.boss = boss
        self.cover = cover
        self.iron = 0
        self.player = Unit(hero.name, hero.hp, hero.max_hp, hero.ac, hero.attack,
                           hero.bonus_damage, hero.spec.weapon, hero.spec.dex + hero.attrs["DEX"],
                           hero.spec.reach, 0)
        self.enemies = []
        for i, name in enumerate(names):
            spec = MONSTERS[name]
            is_boss = boss and i == 0
            hp = spec.hp + (tier - 1) * 7 + (10 + tier * 5 if is_boss else 0)
            self.enemies.append(Unit(name, hp, hp, min(17, spec.ac + (tier - 1) // 3),
                spec.attack + (tier - 1) + int(is_boss), 2 + (tier - 1) + int(is_boss),
                spec.die, spec.dex, spec.reach, min(4, 2 + i),
                spec.ability, spec.effect))
        self._setup_positions()
        self.order = sorted([self.player, *self.enemies],
                            key=lambda u: (roll(self.rng, 1, 20) + u.dex, u.dex), reverse=True)
        self.log.append("Initiative: " + " > ".join(u.name for u in self.order))
        self.index = 0
        self._advance()

    def _setup_positions(self):
        pass

    @property
    def living(self):
        return [u for u in self.enemies if u.alive]

    def _damage(self, target, amount):
        absorbed = min(target.barrier, amount)
        target.barrier -= absorbed
        amount = min(target.hp, amount - absorbed)
        target.hp -= amount
        if absorbed:
            self.log.append(f"Barrier menyerap {absorbed}.")
        if target is self.player and amount and self.hero.class_name == "Warrior" and self.iron < 2:
            self.iron += 1
            target.ac += 1
        if not target.alive:
            self.log.append(f"{target.name} tumbang.")
            if target is not self.player and self.hero.class_name == "Mage":
                self.hero.mana = min(self.hero.max_mana, self.hero.mana + 3)
        return amount

    def _end_check(self):
        if not self.player.alive:
            self.result = "defeat"
        elif not self.living:
            self.result = "victory"
        self.hero.hp = self.player.hp
        return self.result != "ongoing"

    def _check(self, target, dc, ability="dex"):
        bonus = target.dex if ability == "dex" else (
            self.hero.attrs["CON"] + 2 if target is self.player else 2)
        value = roll(self.rng, 1, 20) + bonus
        self.log.append(f"{target.name} save {ability.upper()}: {value} vs DC {dc}.")
        return value >= dc

    def _attack(self, attacker, target, dice=None, advantage=False, special=False, flat=None):
        if not attacker.alive or not target.alive:
            return False
        disadvantage = ("dodge" in target.conditions or "stealth" in target.conditions
                        or ("poison" in attacker.conditions)
                        or (attacker.reach > 2 and attacker.distance(target) <= (1 if isinstance(attacker.pos, tuple) else 0)))
        advantage = advantage or "stealth" in attacker.conditions
        attacker.conditions.pop("stealth", None)
        natural = roll(self.rng, 1, 20)
        if advantage != disadvantage:
            second = roll(self.rng, 1, 20)
            natural = max(natural, second) if advantage else min(natural, second)
        bonus = attacker.attack
        if attacker is self.player:
            if self.hero.class_name == "Swordsman" and attacker.turns <= 2:
                bonus += 2
            if self.hero.class_name == "Archer" and attacker.distance(target) >= 2:
                bonus += 1
        cover = 2 if target.pos in self.cover and attacker.distance(target) >= 2 else 0
        threshold = 18 if (attacker is self.player and self.hero.class_name == "Rogue"
                           and target.hp * 4 <= target.max_hp) else 20
        crit = natural >= threshold
        if natural == 1 or (not crit and natural + bonus < target.armor + cover):
            self.log.append(f"{attacker.name}: d20 {natural}+{bonus} vs AC {target.armor+cover}, MISS.")
            return False
        count, sides = dice or (1, attacker.die)
        dmg = roll(self.rng, count * (2 if crit else 1), sides) + (attacker.damage if flat is None else flat)
        if attacker is self.player and self.hero.class_name == "Cleric" and attacker.turns <= 2:
            dmg += 2
        dealt = self._damage(target, dmg)
        self.log.append(f"{attacker.name}: d20 {natural}+{bonus} vs AC {target.armor+cover}, "
                        f"{'CRIT' if crit else 'HIT'} {target.name} -{dealt} HP.")
        if attacker is self.player and self.hero.class_name == "Lancer":
            attacker.conditions["reflex"] = 1
        if target.alive and attacker.alive and "counter" in target.conditions and target.reaction and target.distance(attacker) <= 1:
            target.reaction = False
            target.conditions.pop("counter", None)
            self.log.append(f"{target.name} melakukan counter!")
            self._attack(target, attacker)
        return True

    def _begin(self, unit):
        unit.turns += 1
        unit.reaction = True
        for name in ("guard", "dodge", "counter", "reflex", "reckless"):
            unit.conditions.pop(name, None)
        for name in ("burn", "bleed"):
            if name in unit.conditions:
                if name in ("burn", "bleed"):
                    self.log.append(f"{unit.name} terkena {name}.")
                    self._damage(unit, 3 if name == "burn" else 2)
                unit.conditions[name] -= 1
                if unit.conditions[name] <= 0:
                    del unit.conditions[name]
                if not unit.alive:
                    break
        if "stun" in unit.conditions:
            del unit.conditions["stun"]
            self.log.append(f"{unit.name} kehilangan giliran (Stun).")
            unit.reaction = False
            return False
        return unit.alive

    def _finish_turn(self, unit):
        unit.conditions.pop("slow", None)
        for name in ("poison", "corrode"):
            if name in unit.conditions:
                unit.conditions[name] -= 1
                if unit.conditions[name] <= 0:
                    del unit.conditions[name]
        self._end_check()
        self.index += 1
        if self.index == len(self.order):
            self.index = 0
            self.round += 1

    def _advance(self):
        while not self._end_check():
            unit = self.order[self.index]
            if not unit.alive:
                self._finish_turn(unit)
                continue
            if not self._begin(unit):
                self._finish_turn(unit)
                continue
            if unit is self.player:
                self.moved = False
                self._reset_movement()
                return
            self._enemy_turn(unit)
            self._finish_turn(unit)

    def _reset_movement(self):
        pass

    def intent(self, enemy):
        # Every 2nd turn is an announced special ability. Boss in phase 2 uses it more often.
        next_turn = enemy.turns + 1
        if self.boss and enemy is self.enemies[0] and enemy.hp * 2 <= enemy.max_hp:
            special = next_turn % 3 != 1
        else:
            special = next_turn % 2 == 0
        return enemy.ability if special else "Basic Attack"

    def _enemy_turn(self, enemy):
        special = self.intent_for_current(enemy)
        if special and enemy.effect in ("guard", "counter"):
            enemy.conditions[enemy.effect] = 1
            enemy.conditions["guard"] = 1
            self.log.append(f"{enemy.name}: {enemy.ability}, posisi bertahan.")
            return
        distance = enemy.distance(self.player)
        if distance > enemy.reach and "slow" not in enemy.conditions:
            self._enemy_move(enemy)
        if enemy.distance(self.player) > enemy.reach:
            return
        if special:
            self.log.append(f"{enemy.name}: {enemy.ability}!")
        hit = self._attack(enemy, self.player, (2, enemy.die) if special and enemy.effect in ("heavy", "stun") else None)
        if hit and special and self.player.alive:
            effect = enemy.effect
            if effect in ("bleed", "corrode", "poison", "stun"):
                if not self._check(self.player, 11 + min(3, enemy.attack // 2), "con"):
                    self.player.conditions[effect] = 1 if effect == "stun" else 3

    def _enemy_move(self, enemy):
        steps = min(2, enemy.distance(self.player) - enemy.reach)
        enemy.pos += steps if self.player.pos > enemy.pos else -steps
        self.log.append(f"{enemy.name} mendekat ke zona {enemy.pos}.")

    def intent_for_current(self, enemy):
        turn = enemy.turns
        if self.boss and enemy is self.enemies[0] and enemy.hp * 2 <= enemy.max_hp:
            return turn % 3 != 1
        return turn % 2 == 0

    def move(self, dest, safe=False):
        p = self.player
        if self.result != "ongoing" or self.moved or "slow" in p.conditions:
            return False, "Gerakan tidak tersedia."
        if not isinstance(dest, int) or not 0 <= dest <= 4 or not 0 < abs(dest - p.pos) <= 2:
            return False, "Pilih zona 0-4, maksimum 2 langkah."
        for enemy in self.living:
            if not safe and enemy.reach <= 2 and enemy.reaction and enemy.distance(p) <= enemy.reach < abs(enemy.pos - dest):
                enemy.reaction = False
                self.log.append(f"Opportunity Attack: {enemy.name}!")
                self._attack(enemy, p)
                if self._end_check():
                    return True, "Kamu tumbang saat bergerak."
        p.pos = dest
        self.moved = True
        return True, f"Bergerak ke zona {dest}."

    def _dash(self, target):
        self.player.pos = target.pos

    def _push(self, enemy):
        p = self.player
        enemy.pos = max(0, min(4, enemy.pos + (1 if enemy.pos >= p.pos else -1)))

    def skill_reason(self, skill):
        if skill not in self.hero.skills:
            return "Skill belum terbuka."
        left = self.cooldowns.get(skill.name, 0) - self.player.turns
        if left > 0:
            return f"Cooldown {left} giliran."
        if getattr(self.hero, skill.kind) < skill.cost:
            return f"{skill.kind} tidak cukup."
        return ""

    def _cast(self, skill: Skill, target):
        p, h = self.player, self.hero
        reason = self.skill_reason(skill)
        if reason:
            return False, reason
        effect = skill.effect
        if skill.dice[0] and (target not in self.living or p.distance(target) > skill.reach):
            return False, "Target tidak hidup atau di luar jangkauan."
        setattr(h, skill.kind, getattr(h, skill.kind) - skill.cost)
        self.cooldowns[skill.name] = p.turns + skill.cooldown + 1
        self.log.append(f"{h.name} menggunakan {skill.name}.")
        if effect in ("heal", "sanctuary"):
            hp = min(p.max_hp - p.hp, roll(self.rng, 3 if effect == "sanctuary" else 2, 6) + h.level)
            p.hp += hp
            p.conditions["guard"] = 1
            if effect == "sanctuary":
                for status in ("poison", "bleed", "burn", "corrode", "slow"):
                    p.conditions.pop(status, None)
                p.barrier = max(p.barrier, 8 + h.level)
            self.log.append(f"Pulih {hp} HP.")
        elif effect == "barrier":
            p.barrier = max(p.barrier, 8 + h.level * 2)
        elif effect in ("stealth", "counter"):
            p.conditions[effect] = 1
            if effect == "counter":
                p.conditions["guard"] = 1
        else:
            if effect == "dash":
                self._dash(target)
            targets = [e for e in self.living if p.distance(e) <= skill.reach] if effect in ("area", "area_save") else [target]
            for enemy in targets:
                if not p.alive:
                    break
                if effect in ("radiant", "area_save"):
                    dmg = roll(self.rng, *skill.dice) + p.damage
                    if effect == "radiant" and "Skeleton" in enemy.name:
                        dmg += 4
                    save = self._check(enemy, 10 + h.attack)
                    self.log.append(f"{enemy.name} terkena {self._damage(enemy, dmg // 2 if save else dmg)} damage.")
                    continue
                if effect == "triple":
                    hits = [self._attack(p, enemy, skill.dice, flat=max(1, p.damage // 2))
                            for _ in range(3) if enemy.alive and p.alive]
                    hit = any(hits)
                else:
                    hit = self._attack(p, enemy, skill.dice, advantage=effect in ("advantage", "reckless"))
                if hit and enemy.alive:
                    status = {"burn": ("burn", 2), "bleed": ("bleed", 2),
                              "slow": ("slow", 1), "triple": ("corrode", 2)}.get(effect)
                    if status:
                        enemy.conditions[status[0]] = status[1]
                    if effect == "stun" and not self._check(enemy, 10 + h.attack, "con"):
                        enemy.conditions["stun"] = 1
                    if effect == "push":
                        self._push(enemy)
            if effect == "push":
                p.conditions["guard"] = 1
            if effect == "reckless":
                p.conditions["reckless"] = 1
            if effect == "bulwark":
                p.barrier = max(p.barrier, 6 + h.level)
                p.conditions["guard"] = 1
        return True, ""

    def act(self, action, target=None, skill=None, dest=None):
        if self.result != "ongoing":
            return False, "Pertarungan sudah berakhir."
        p, h = self.player, self.hero
        if action == "attack":
            if target not in self.living or p.distance(target) > p.reach:
                return False, "Target tidak hidup atau di luar jangkauan."
            self._attack(p, target)
        elif action == "skill":
            if skill is None:
                return False, "Pilih skill."
            ok, msg = self._cast(skill, target)
            if not ok:
                return False, msg
        elif action == "guard":
            p.conditions["dodge"] = 1
            h.stamina = min(h.max_stamina, h.stamina + 2)
        elif action == "disengage":
            ok, msg = self.move(dest, safe=True)
            if not ok:
                return False, msg
        elif action == "potion":
            if h.potions <= 0 or p.hp == p.max_hp:
                return False, "Tidak ada potion atau HP sudah penuh."
            h.potions -= 1
            p.hp = min(p.max_hp, p.hp + roll(self.rng, 2, 6) + 6 + h.level)
        elif action == "flee":
            if roll(self.rng, 1, 20) + p.dex >= 12 + int(self.boss) * 2:
                self.result = "fled"
                h.hp = p.hp
                return True, "Berhasil kabur."
            self.log.append("Gagal kabur; giliran terpakai.")
        else:
            return False, "Aksi tidak dikenal."
        self._finish_turn(p)
        if self.result == "ongoing":
            self._advance()
        return True, ""
