"""Original ASCII character sprites, each drawn on a 13 x 7 stage.
Idle, anticipation and release are separate drawings, not just color changes.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Sprite:
    tone: str
    idle: tuple
    ready: tuple
    strike: tuple
    style: str


def art(*rows):
    assert len(rows) == 7 and all(len(r) <= 13 for r in rows), rows
    return tuple(r.ljust(13) for r in rows)


HEROES = {
    'Swordsman': Sprite('cyan',
        art('    .-.     /','   (o_o)   / ','   /[=]\\  /  ','  / | |\\_/   ','    |=|      ','   /   \\     ','  _/   \\_    '),
        art('   .-.   /   ','  (o_o) /    ','  /[=]\\/     ',' / | |/      ','   |=|       ','  /   \\      ',' _/   \\_     '),
        art('     .-.     ','    (o_o)    ','   /[=]======','  / | |      ','    |=|      ','   /   \\     ',' _/     \\_   '), 'slash'),
    'Lancer': Sprite('blue',
        art('    /\\    ^  ','   (o )   |  ','   /[+]\\  |  ','  / | |\\_|  ','    |=|   |  ','   /   \\  |  ','  _/   \\_ |  '),
        art('    /\\       ','   (o )      ','   /[+]\\     ','<======\\     ','    |=|      ','   /   \\     ',' _/     \\_   '),
        art('     /\\      ','    (o )     ','    /[+]\\    ','   /=========','     |=|     ','   _/  \\     ',' _/     \\_   '), 'thrust'),
    'Cleric': Sprite('gold',
        art('    _+_   +  ','   (o o)  |  ','   /[+]\\  |  ','  /  | \\_|  ','    / \\   |  ','   /___\\  |  ','   _/ \\_  |  '),
        art('   + + +     ','    _+_      ','   (o o) +   ','  /[+]\\_/    ','    / \\      ','   /___\\     ','   _/ \\_     '),
        art('        +    ','    _+_ | +  ','   (o o)|/   ','   /[+]===== ','    / \\      ','   /___\\     ','   _/ \\_     '), 'holy'),
    'Mage': Sprite('purple',
        art('     /\\   *  ','   _/  \\_ |  ','    (..)  |  ','   /{*}\\__|  ','    /  \\  |  ','   /____\\ |  ','   _/  \\_ |  '),
        art('    /\\   .   ','  _/  \\_ *   ','   (..)  |   ','  /{*}\\_/    ','    /  \\     ','   /____\\    ','   _/  \\_    '),
        art('     /\\    * ','   _/  \\_ o  ','    (..)  /  ','   /{*}====* ','    /  \\     ','   /____\\    ','   _/  \\_    '), 'magic'),
    'Rogue': Sprite('green',
        art('    .--.     ','   /_.._\\    ','   \\_==_/   /','   /{x}\\   / ','  / | |\\__/  ','   /   \\     ','  _/   \\_    '),
        art('             ','    .--.     ','   /_.._\\  / ','   \\_==_/ /  ','  _/{x}\\_/   ',' /_    \\     ','   \\____\\_   '),
        art('             ','      .--.   ','     /_.._\\  ','    _\\_==_/=>',' ___/{x}==>  ','/____  \\     ','     \\__\\_   '), 'dash'),
    'Archer': Sprite('green',
        art('    .-.  )   ','   (o_o)  )  ','   /[>]\\  |  ','  / | |\\_)  ','    |=|  )   ','   /   \\     ','  _/   \\_    '),
        art('    .-.  )   ','   (o_o) /)  ','   /[>]\\/ |  ','  <----+--|  ','    |=| \\)   ','   /   \\     ','  _/   \\_    '),
        art('    .-.  )   ','   (o_o)  )  ','   /[>]\\  |  ','  / | |======','    |=|  )   ','   /   \\     ','  _/   \\_    '), 'arrow'),
    'Warrior': Sprite('gold',
        art('    .---.    ','   |o _ o|   ','   [=====]   ','  /[###]\\__  ','  |[###]|[]| ','   /   \\|__| ','  _/   \\_    '),
        art('    .---.    ','   |o _ o|   ','  /[=====]   ',' / [###]__[ ]','   [###]|###|','   /   \\|___|',' _/     \\_   '),
        art('     .---.   ','    |o _ o|  ','    [=====]  ','   /[###]____','    [###]|##|','   _/  \\ |__|',' _/     \\_   '), 'bash'),
}

# Enemies face left (the renderer mirrors the poses automatically).
def foe(idle, ready, strike, style='slash', tone='red'):
    return Sprite(tone, art(*idle), art(*ready), art(*strike), style)

SKELETON = foe(
    ('    .---.    ','   (x   x)   ','    \\_n_/   /','   /-+-\\   / ','     | \\__/  ','    / \\      ','   _/ \\_     '),
    ('    .---.  / ','   (x   x)/  ','    \\_n_/ /  ','   /-+-\\_/   ','     |       ','    / \\      ','   _/ \\_     '),
    ('     .---.   ','    (x   x)  ','     \\_n_/   ','    /-+-=====','      |      ','    _/ \\     ','  _/    \\_   '))
GOBLIN = foe(
    ('   /\\_/\\     ','  <o   o>    ','   \\_v_/     ','   /[x]\\  /  ','    |=|\\_/   ','   /   \\     ','  _/   \\_    '),
    ('             ','   /\\_/\\     ','  <o   o> /  ','   \\_v_/ /   ','   /[x]\\/    ','  /_  /      ','    \\_\\_     '),
    ('             ','     /\\_/\\   ','    <o   o>  ','     \\_v_/==>','    /[x]===  ','   /_  \\     ','     \\__\\_   '), 'dash')
SLIME = foe(
    ('             ','             ','      .--.   ','    .(    ). ','   / o    o \\','  /    __    ','  \\_________/'),
    ('             ','             ','             ','    ______   ','  _/o    o\\_ ',' /    __    \\',' \\__________/'),
    ('        .-.  ','      .(   ).','     / o  o \\','    /   __   ','    \\_______/','             ','             '), 'slam', 'green')
MIMIC = foe(
    ('   _______   ','  / _____ \\  ',' | | o o | | ',' | |_____| | ',' |  /   \\  | ',' | /_____\\ | ','  \\_______/  '),
    ('   _______   ','  / _____ \\  ',' | | * * | | ',' | |_____| | ',' |  /   \\  | ',' | /_____\\ | ','  \\_______/  '),
    ('   _______ * ','  / _____ \\  ',' | | * * | | ',' | |=====|==>',' |  /   \\  | ',' | /_____\\ | ','  \\_______/  '), 'magic','purple')

# Distinct variants retain family silhouettes while adding equipment.
ENEMIES = {'Low Rank Slime': SLIME, 'Medium Slime': Sprite('purple', SLIME.idle, SLIME.ready, SLIME.strike, 'slam'),
           'Skeleton': SKELETON, 'Goblin': GOBLIN, 'Mirror Mimic': MIMIC,
           'Goblin Archer': Sprite('red', art('   /\\_/\\  )  ','  <o   o>  ) ','   \\_v_/   | ','   /[>]\\___| ','    |=|  )   ','   /   \\     ','  _/   \\_    '), HEROES['Archer'].ready, HEROES['Archer'].strike, 'arrow'),
           'Goblin Warrior': Sprite('red', art('   /\\_/\\     ','  <o   o>    ','   [===]     ','  /[###]__   ','   [###]|[]| ','   /   \\|__| ','  _/   \\_    '), HEROES['Warrior'].ready, HEROES['Warrior'].strike, 'bash'),
           'Skeleton Armor': Sprite('white', art('    .---.    ','   (x   x) + ','    \\_n_/  | ','   /[###]\\_| ','    [###]  | ','    /   \\  | ','   _/   \\_ | '), HEROES['Cleric'].ready, HEROES['Cleric'].strike, 'holy'),
           'Goblin Captain': Sprite('gold', art('    ^^^^     ','   /\\_/\\     ','  <o   o>  / ','   [===]  /  ','  /[###]\\/   ','   /   \\     ','  _/   \\_    '), GOBLIN.ready, SKELETON.strike, 'slash'),
           'Giant Skeleton': Sprite('white', art('   .-----.   ','  ( X   X )  ','   \\__n__/  #','  /==+==\\  ##',' /   |   \\_##','    / \\      ','  _/   \\_    '), SKELETON.ready, HEROES['Warrior'].strike, 'bash')}

# Keep monster heads recognizable during equipment-specific poses.
for _name in ('Goblin Archer','Goblin Warrior','Skeleton Armor','Goblin Captain','Giant Skeleton'):
    _s=ENEMIES[_name]
    ENEMIES[_name]=Sprite(_s.tone,_s.idle,_s.idle[:3]+_s.ready[3:],_s.idle[:3]+_s.strike[3:],_s.style)

MIRROR = str.maketrans('/\\<>()[]{}', '\\/><)(][}{')

def pose(sprite, name='idle', flip=False, step=0):
    rows = list(getattr(sprite, name, sprite.idle))
    if name == 'walk' and sprite.style != 'slam':
        rows[-2:] = art('', '', '', '', '', '    /|       ' if step%2 else '     |\\      ', '   _/ \\_     ' if step%2 else '    _/ \\_    ')[-2:]
    elif name == 'walk' and sprite.style == 'slam':
        rows = list(sprite.strike if step%2 else sprite.ready)
    elif name == 'hurt':
        rows = [' '*13] + [r[:12].rjust(13) for r in sprite.idle[:-1]]
    elif name == 'down':
        rows = list(art('', '', '', '', '  . .        ', '  _/==x==\\_  ', '  __________ '))
    elif name == 'guard':
        rows = list(sprite.ready); rows[3] = '   /[||||]   '; rows[4] = '    [||||]   '
    elif name == 'win':
        rows = list(sprite.idle); rows[0] = '  *  *  *    '; rows[3] = '  \\  |  /    '
    if flip:
        rows = [r.translate(MIRROR)[::-1] for r in rows]
    return rows
