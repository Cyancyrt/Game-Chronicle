"""Versioned, atomic saves with explicit legacy import."""
import json
import os
from dataclasses import asdict
from pathlib import Path
from .models import Hero, MAX_LEVEL
from .content import CLASSES, ATTRIBUTES, FLOORS
from .world import ROOMS

SAVE = Path(__file__).resolve().parent.parent / "saves" / "balanced_classic.json"
VERSION = 2


def save(hero, path=SAVE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump({"version": VERSION, "hero": asdict(hero)}, file, indent=2, ensure_ascii=False)
        file.flush()
        os.fsync(file.fileno())
    temporary.replace(path)


def validate(hero):
    if hero.class_name not in CLASSES or not isinstance(hero.name, str) or not hero.name.strip():
        raise ValueError("Nama/class tidak valid.")
    for key in ("level", "xp", "points", "floor", "hp", "mana", "stamina", "gold", "potions", "wins", "defeats"):
        value = getattr(hero, key)
        if type(value) is not int or value < 0:
            raise ValueError(f"Save tidak valid: {key}.")
    if not 1 <= hero.level <= MAX_LEVEL or not 0 <= hero.floor < len(FLOORS):
        raise ValueError("Level/lantai di luar jangkauan.")
    if not isinstance(hero.attrs, dict) or set(hero.attrs) != set(ATTRIBUTES) or any(type(v) is not int or not 0 <= v <= 5 for v in hero.attrs.values()):
        raise ValueError("Atribut tidak valid.")
    if hero.room not in ROOMS or any(not isinstance(v, list) or any(k not in ROOMS for k in v) or len(v) != len(set(v)) for v in (hero.cleared, hero.visited)):
        raise ValueError("Peta save tidak valid.")
    if (hero.room not in hero.visited or not set(hero.cleared) <= set(hero.visited)
            or ("G" in hero.visited and not set("ABC") <= set(hero.cleared))
            or not set(hero.cleared) <= set("ABCGT")):
        raise ValueError("Progress ruangan tidak valid.")
    if type(hero.rested) is not bool or type(hero.finished) is not bool or hero.finished != (hero.floor == len(FLOORS)-1 and "G" in hero.cleared):
        raise ValueError("Status dungeon tidak valid.")
    if not 1 <= hero.hp <= hero.max_hp or hero.mana > hero.max_mana or hero.stamina > hero.max_stamina:
        raise ValueError("Resource save tidak valid.")
    if hero.xp >= hero.xp_needed:
        raise ValueError("XP tidak valid.")
    return hero


def load(path=SAVE):
    with Path(path).open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict) or data.get("version") != VERSION:
        raise ValueError("Versi save tidak didukung. Gunakan import legacy untuk save lama.")
    return validate(Hero(**data["hero"]))


def import_legacy(path):
    with Path(path).open(encoding="utf-8") as file:
        old = json.load(file)
    hero = Hero.create(old["name"], old["player_class"])
    hero.level = max(1, min(MAX_LEVEL, int(old.get("level", 1))))
    hero.points = (hero.level - 1) * 2
    hero.xp = max(0, min(hero.xp_needed - 1, int(old.get("exp", 0))))
    hero.floor = max(0, min(len(FLOORS)-1, int(old.get("world", {}).get("current_level", 1)) - 1))
    hero.restore()
    return validate(hero)
