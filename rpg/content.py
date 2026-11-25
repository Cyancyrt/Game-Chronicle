"""Immutable game definitions. Numbers here are the balance knobs."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    name: str
    level: int
    cost: int
    cooldown: int
    kind: str
    dice: tuple[int, int] = (0, 0)
    reach: int = 1
    effect: str = ""
    description: str = ""


@dataclass(frozen=True)
class ClassSpec:
    role: str
    hp: int
    ac: int
    attack: int
    dex: int
    mana: int
    stamina: int
    weapon: int
    reach: int
    passive: str
    passive_desc: str
    skills: tuple[Skill, ...]


CLASSES = {
    "Swordsman": ClassSpec("Petarung seimbang", 42, 15, 6, 2, 11, 15, 8, 1,
        "Battle Instinct", "+2 attack roll pada dua giliran pertama.", (
        Skill("Power Slash", 1, 3, 1, "stamina", (2, 8), 1, "", "Tebasan kuat."),
        Skill("Whirlwind", 3, 4, 2, "stamina", (1, 8), 1, "area", "Serang semua musuh dalam jangkauan."),
        Skill("Riposte", 5, 4, 2, "stamina", effect="counter", description="Bertahan dan balas serangan jarak dekat."),
        Skill("Blade Storm", 7, 7, 3, "stamina", (3, 6), 1, "area", "Tebasan besar terhadap semua musuh sekitar."))),
    "Lancer": ClassSpec("Kontrol jarak", 36, 14, 5, 3, 8, 16, 8, 2,
        "Swift Reflex", "+1 AC setelah mengenai musuh, sampai giliran berikutnya.", (
        Skill("Triple Jab", 1, 3, 1, "stamina", (1, 4), 2, "triple", "Tiga tusukan independen; armor musuh terbuka jika terkena."),
        Skill("Impale", 3, 4, 2, "stamina", (2, 6), 2, "bleed", "Tusukan yang menyebabkan Bleed."),
        Skill("Phalanx", 5, 4, 2, "stamina", (2, 6), 2, "push", "Dorong musuh menjauh dan tambah Guard."),
        Skill("Piercing Charge", 7, 6, 2, "stamina", (3, 8), 3, "dash", "Terjang target tanpa opportunity attack."))),
    "Cleric": ClassSpec("Penyembuh tangguh", 35, 14, 4, 1, 18, 10, 6, 2,
        "Force Boost", "+2 damage pada dua giliran pertama.", (
        Skill("Low Healing", 1, 4, 1, "mana", effect="heal", description="Pulihkan 2d6 + level HP dan Guard."),
        Skill("Sacred Flame", 3, 4, 1, "mana", (2, 8), 3, "radiant", "Saving throw DEX; setengah damage jika sukses. Kuat melawan Skeleton."),
        Skill("Sanctuary", 5, 6, 3, "mana", effect="sanctuary", description="Pulihkan 3d6 + level HP, bersihkan efek buruk, pasang Barrier."),
        Skill("Divine Judgment", 7, 8, 2, "mana", (3, 8), 3, "radiant", "Sihir suci dengan saving throw DEX."))),
    "Mage": ClassSpec("Caster dan area damage", 31, 13, 4, 2, 22, 9, 6, 3,
        "Mana Surge", "Pulihkan 3 MP saat membunuh musuh.", (
        Skill("Fireball", 1, 5, 1, "mana", (2, 6), 3, "burn", "Api dan Burn pada target yang terkena."),
        Skill("Frost Lance", 3, 4, 1, "mana", (2, 6), 3, "slow", "Kurangi mobilitas musuh satu giliran."),
        Skill("Chain Lightning", 5, 7, 2, "mana", (2, 6), 3, "area_save", "Semua musuh dalam jangkauan melakukan saving throw."),
        Skill("Meteor", 7, 10, 3, "mana", (3, 8), 4, "area_save", "Damage area tinggi, setengah pada saving throw DEX sukses."))),
    "Rogue": ClassSpec("Mobilitas dan eksekusi", 31, 14, 5, 4, 8, 14, 8, 1,
        "Final Blow", "Critical pada roll 18-20 jika HP target <= 25%.", (
        Skill("Stealth", 1, 3, 1, "stamina", effect="stealth", description="Disadvantage bagi musuh; advantage pada serangan berikutnya."),
        Skill("Sneak Attack", 3, 3, 1, "stamina", (2, 8), 1, "advantage", "Serangan dengan advantage."),
        Skill("Shadowstrike", 5, 5, 2, "stamina", (3, 6), 3, "dash", "Mendekat tanpa opportunity attack lalu menyerang."),
        Skill("Assassinate", 7, 6, 3, "stamina", (3, 8), 1, "advantage", "Serangan mematikan dengan advantage."))),
    "Archer": ClassSpec("Penyerang jarak jauh", 32, 13, 5, 4, 8, 13, 8, 4,
        "Marksmanship", "+1 attack roll pada jarak 2 atau lebih.", (
        Skill("Eagle Eye", 1, 3, 1, "stamina", (2, 8), 4, "advantage", "Tembakan presisi dengan advantage."),
        Skill("Pinning Shot", 3, 3, 1, "stamina", (2, 6), 4, "slow", "Serangan yang menghentikan gerakan target."),
        Skill("Volley", 5, 5, 2, "stamina", (2, 6), 4, "area", "Hujan panah pada seluruh musuh dalam jangkauan."),
        Skill("Hunter's Mark", 7, 6, 2, "stamina", (3, 8), 4, "bleed", "Tembakan kuat dan Bleed."))),
    "Warrior": ClassSpec("Tank dan mitigasi", 40, 14, 4, 1, 8, 13, 8, 1,
        "Iron Will", "+1 AC setelah menerima damage, maksimum +2.", (
        Skill("Barrier", 1, 4, 1, "stamina", effect="barrier", description="Serap 8 + 2 x level damage."),
        Skill("Shield Bash", 3, 4, 2, "stamina", (2, 6), 1, "stun", "Stun jika target gagal saving throw CON."),
        Skill("Reckless Strike", 5, 4, 1, "stamina", (3, 6), 1, "reckless", "Damage tinggi dengan advantage; pertahanan terbuka."),
        Skill("Bulwark", 7, 6, 3, "stamina", (2, 8), 1, "bulwark", "Serang dan siapkan Barrier serta Guard."))),
}


@dataclass(frozen=True)
class MonsterSpec:
    hp: int
    ac: int
    attack: int
    die: int
    dex: int
    reach: int
    ability: str
    effect: str


MONSTERS = {
    "Low Rank Slime": MonsterSpec(16, 10, 2, 4, 0, 1, "Acid Touch", "corrode"),
    "Skeleton": MonsterSpec(20, 12, 3, 6, 1, 1, "Rusty Slash", "bleed"),
    "Goblin": MonsterSpec(17, 12, 3, 6, 3, 2, "Throwing Knife", "heavy"),
    "Goblin Warrior": MonsterSpec(27, 13, 3, 6, 1, 1, "Shield Block", "guard"),
    "Medium Slime": MonsterSpec(30, 12, 4, 6, 0, 1, "Slam Jump", "stun"),
    "Goblin Archer": MonsterSpec(21, 12, 4, 6, 3, 4, "Poison Arrow", "poison"),
    "Skeleton Armor": MonsterSpec(32, 14, 4, 8, 0, 1, "Grave's Blessing", "guard"),
    "Goblin Captain": MonsterSpec(36, 14, 5, 8, 2, 1, "Counter Stance", "counter"),
    "Mirror Mimic": MonsterSpec(25, 12, 4, 6, 2, 3, "Echo", "heavy"),
    "Giant Skeleton": MonsterSpec(44, 14, 5, 8, 0, 1, "Bone Crusher", "stun"),
}


@dataclass(frozen=True)
class Floor:
    name: str
    encounters: tuple[str, str, str]
    boss: str
    recommended: int
    lore: str
    room_names: tuple[str, str, str, str, str]
    cover: tuple[int, ...]


FLOORS = (
    Floor("Gerbang Lumut", ("Low Rank Slime", "Goblin", "Skeleton"), "Goblin Warrior", 1,
          "Jejak pasukan goblin menghilang ke bawah reruntuhan.",
          ("Lorong Lumut", "Pos Pengintai", "Makam Penjaga", "Altar Daun", "Camp Pengelana"), (3,)),
    Floor("Gua Racun", ("Skeleton", "Goblin", "Goblin Warrior"), "Medium Slime", 2,
          "Kabut asam memenuhi lorong dan mengaburkan jalan.",
          ("Gua Kristal", "Sarang Goblin", "Kolam Asam", "Altar Lumut", "Camp Kristal"), (1, 3)),
    Floor("Katakomba", ("Skeleton", "Goblin Archer", "Goblin Warrior"), "Skeleton Armor", 4,
          "Tulang-tulang bergerak di bawah altar kuno.",
          ("Kubah Tulang", "Lorong Panah", "Ossuary", "Altar Jiwa", "Camp Makam"), (2,)),
    Floor("Benteng Goblin", ("Medium Slime", "Goblin Archer", "Skeleton Armor"), "Goblin Captain", 5,
          "Kapten menjaga kunci menuju ruang terdalam.",
          ("Gudang Senjata", "Menara Pemanah", "Barak Kapten", "Altar Perang", "Camp Benteng"), (1, 4)),
    Floor("Makam Raja Tulang", ("Skeleton Armor", "Goblin Warrior", "Goblin Archer"), "Giant Skeleton", 7,
          "Kutukan sang raja tulang menanti untuk dipatahkan.",
          ("Aula Penjaga", "Ruang Legiun", "Ruang Kutukan", "Altar Raja", "Camp Terakhir"), (2, 4)),
)

ATTRIBUTES = {"STR": "Damage Swordsman/Lancer/Warrior", "DEX": "Initiative, AC, damage Rogue/Archer dan kabur",
              "CON": "HP, stamina dan saving throw", "INT": "MP dan damage Mage",
              "WIS": "MP, damage Cleric dan skill check", "CHA": "Skill check altar dan diskon potion"}
