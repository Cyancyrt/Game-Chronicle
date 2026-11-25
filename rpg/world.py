"""Dungeon graph, exploration and exactly-once encounter rewards."""
from .content import FLOORS
from .combat import Battle, roll

ROOMS = {
    "E": ("Entrance", ("A", "B")),
    "A": ("Ruang Penjaga 1", ("E", "C", "T")),
    "B": ("Ruang Penjaga 2", ("E", "C", "R")),
    "C": ("Ruang Segel", ("A", "B", "G")),
    "T": ("Altar rahasia", ("A",)),
    "R": ("Camp", ("B",)),
    "G": ("Gerbang Boss", ("C",)),
}
ENCOUNTERS = ("A", "B", "C", "G")


class Dungeon:
    def __init__(self, hero, rng):
        self.hero = hero
        self.rng = rng
        self.active_battle = None

    @property
    def floor(self):
        return FLOORS[self.hero.floor]

    @property
    def unlocked(self):
        return all(room in self.hero.cleared for room in ("A", "B", "C"))

    @property
    def pending(self):
        return self.hero.room in ENCOUNTERS and self.hero.room not in self.hero.cleared

    def room_name(self, room):
        return self.floor.room_names["ABCTR".index(room)] if room in "ABCTR" else ROOMS[room][0]

    def map_text(self):
        h = self.hero
        def mark(room):
            if room == h.room:
                return f"[{room}*]"
            if room == "G" and not self.unlocked:
                return "[G#]"
            if room in h.cleared:
                return f"[{room}+]"
            return f"[{room}{'.' if room in h.visited else '?'}]"
        a, b, c, t, r, g, e = (mark(k) for k in "ABCTRGE")
        return (f"LANTAI {h.floor + 1}/{len(FLOORS)} | {self.floor.name}\n"
                f" {t}--{a}------+\n"
                f"        |        |\n"
                f"       {e}      {c}--{g}\n"
                f"        |        |\n"
                f" {r}--{b}------+\n"
                "* Lokasi | + Selesai | ? Belum dikunjungi | . Dikunjungi | # Terkunci\n"
                f"Segel: {sum(k in h.cleared for k in 'ABC')}/3"
                f" | Boss: {self.floor.boss} | Rekomendasi Lv {self.floor.recommended}\n"
                f"Lokasi: {self.room_name(h.room)} | Cover medan: " + ", ".join(f"Z{p}" for p in self.floor.cover)
                + "\n" + " | ".join(f"{room}: {self.room_name(room)}" for room in "ABCTR"))

    def move(self, dest):
        h = self.hero
        if h.finished or self.pending:
            return False, "Selesaikan encounter dahulu."
        if dest not in ROOMS[h.room][1]:
            return False, "Ruangan tidak terhubung."
        if dest == "G" and not self.unlocked:
            return False, "Gerbang terkunci: kalahkan penjaga A, B, C."
        h.room = dest
        if dest not in h.visited:
            h.visited.append(dest)
        return True, self.room_name(dest)

    def encounter(self):
        if not self.pending:
            raise ValueError("Tidak ada encounter aktif.")
        if self.active_battle is not None:
            return self.active_battle
        h = self.hero
        tier = self.floor.recommended
        if h.room == "G":
            self.active_battle = Battle(h, [self.floor.boss], tier, boss=True, rng=self.rng, cover=self.floor.cover)
            return self.active_battle
        index = ("A", "B", "C").index(h.room)
        names = [self.floor.encounters[index]]
        if h.floor >= 2 and index == 2:
            names.append("Low Rank Slime" if h.floor == 2 else "Goblin")
        if h.floor == 4 and index == 1:
            names.append("Skeleton")
        self.active_battle = Battle(h, names, tier, rng=self.rng, cover=self.floor.cover)
        return self.active_battle

    def resolve(self, battle):
        h = self.hero
        if battle is not self.active_battle or not self.pending or battle.result not in ("victory", "defeat", "fled"):
            raise ValueError("Encounter tidak valid atau belum selesai.")
        self.active_battle = None
        if battle.result == "victory":
            boss = h.room == "G"
            h.cleared.append(h.room)
            h.wins += 1
            amount = (50 if boss else 26) + self.floor.recommended * 4 + (len(battle.enemies) - 1) * 10
            coins = 16 if boss else 8
            h.gold += coins
            h.recover()
            if boss or h.room == "C":
                h.potions += 1
            messages = [f"Menang! +{amount} XP, +{coins} gold. Sebagian HP dan resource pulih."]
            messages += h.gain_xp(amount)
            if boss and h.floor == len(FLOORS) - 1:
                h.finished = True
                messages.append("Kutukan dipatahkan! Dungeon selesai. Selamat, Adventurer!")
            elif boss:
                messages.append("Boss dikalahkan! Pilih N untuk turun ke lantai berikutnya.")
            return messages
        if battle.result == "defeat":
            h.defeats += 1
            lost = min(8, h.gold)
            h.gold -= lost
            h.restore()
            h.room = "E"
            return [f"Kamu diselamatkan ke Entrance. Kehilangan {lost} gold. Segel tetap tersimpan."]
        h.room = "E"
        return ["Kabur ke Entrance. Musuh belum dikalahkan; reward tidak diberikan."]

    def advance(self):
        h = self.hero
        if h.room != "G" or "G" not in h.cleared or h.finished:
            return False
        h.floor += 1
        h.room, h.cleared, h.visited, h.rested = "E", [], ["E"], False
        h.restore()
        return True

    def rest(self):
        h = self.hero
        if self.pending or h.room != "R" or h.rested:
            return False
        h.rested = True
        h.restore()
        return True

    def altar(self, attr):
        h = self.hero
        if h.room != "T" or "T" in h.cleared or attr not in ("WIS", "CHA", "INT"):
            return False, "Altar tidak tersedia."
        h.cleared.append("T")
        total = roll(self.rng, 1, 20) + 2 + h.attrs[attr]
        if total >= 11:
            h.gold += 12
            h.potions += 2
            h.recover()
            return True, f"{attr} check {total} vs DC 11: berhasil. +12 gold, +2 potion."
        h.hp = max(1, h.hp - 4)
        h.potions += 1
        return True, f"{attr} check {total} vs DC 11: gagal. -4 HP, tetapi menemukan 1 potion."

    def buy_potion(self):
        if self.hero.room not in ("E", "R") or self.hero.gold < self.potion_price or self.pending:
            return False
        self.hero.gold -= self.potion_price
        self.hero.potions += 1
        return True

    @property
    def potion_price(self):
        return 10 - self.hero.attrs["CHA"]

    def use_potion(self):
        h = self.hero
        if self.pending or h.potions <= 0 or h.hp >= h.max_hp:
            return False
        h.potions -= 1
        h.hp = min(h.max_hp, h.hp + 14 + h.level)
        return True
