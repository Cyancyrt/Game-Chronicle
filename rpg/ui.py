"""Dependency-free terminal presentation. All rendering is separate from the game engine."""
import os
import re
import shutil
import sys
import textwrap
import unicodedata

ANSI = re.compile(r'\x1b\[[0-9;]*m')
PALETTE = {'gold': '93', 'cyan': '96', 'green': '92', 'red': '91', 'blue': '94',
           'purple': '95', 'muted': '90', 'bold': '1', 'white': '97'}


def safe(value):
    # Never let a character name or save data inject terminal control sequences.
    return ''.join(c if unicodedata.category(c)[0] != 'C' else '?' for c in str(value))


def visible(text):
    return ANSI.sub('', text)


def cell_width(text):
    return sum(0 if unicodedata.combining(c) else 2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1
               for c in visible(text))


def pad(text, width):
    return text + ' ' * max(0, width - cell_width(text))


def wrap(text, width):
    if cell_width(text) <= width:
        return [text]
    # Wrapped strings are deliberately plain, preventing unterminated ANSI styles.
    result = []
    for line in textwrap.wrap(visible(text), max(1, width)) or ['']:
        while cell_width(line) > width:
            n = 1
            while n < len(line) and cell_width(line[:n + 1]) <= width:
                n += 1
            result.append(line[:n]); line = line[n:]
        result.append(line)
    return result


def enable_ansi():
    if not sys.stdout.isatty() or os.environ.get('TERM') == 'dumb':
        return False
    if os.name != 'nt':
        return True
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        from ctypes import wintypes
        kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        handle = kernel.GetStdHandle(wintypes.DWORD(-11))
        mode = wintypes.DWORD()
        return bool(kernel.GetConsoleMode(handle, ctypes.byref(mode)) and
                    kernel.SetConsoleMode(handle, mode.value | 0x0004))
    except (AttributeError, OSError):
        return False


class Terminal:
    def __init__(self, plain=False, no_clear=False, ascii_only=False, width=None):
        self.tty = sys.stdout.isatty()
        self.ansi = not plain and enable_ansi()
        self.color = self.ansi and 'NO_COLOR' not in os.environ
        self.clear = self.tty and not (no_clear or plain)
        self.fixed_width = width
        self.animation = True
        self.animation_speed = 1.0
        self.ascii = plain or ascii_only or not self.tty
        if not self.ascii:
            try:
                '╭─╮│╰╯█░◆'.encode(sys.stdout.encoding or 'ascii')
            except (UnicodeError, LookupError):
                self.ascii = True

    @property
    def width(self):
        return max(24, min(118, self.fixed_width or shutil.get_terminal_size((92, 30)).columns - 1))

    @property
    def height(self):
        return shutil.get_terminal_size((92, 30)).lines

    def paint(self, text, tone='white'):
        text = str(text)
        return f'\x1b[{PALETTE[tone]}m{text}\x1b[0m' if self.color else text

    def meter(self, current, maximum, size=12, tone='green'):
        filled = max(0, min(size, round(size * current / maximum))) if maximum else 0
        a, b = ('#', '.') if self.ascii else ('█', '░')
        return self.paint(a * filled, tone) + self.paint(b * (size-filled), 'muted') + f' {current}/{maximum}'

    def panel(self, title, lines, width=None, tone='gold'):
        width = width or self.width
        tl, tr, bl, br, h, v = ('+', '+', '+', '+', '-', '|') if self.ascii else ('╭', '╮', '╰', '╯', '─', '│')
        inner = width - 4
        label = ' ' + title + ' ' if title else ''
        if cell_width(label) > width - 2:
            label = ''
        top = self.paint(tl + h, tone) + self.paint(label, tone) + self.paint(h * (width - 3 - cell_width(label)) + tr, tone)
        body = []
        for line in lines:
            for part in wrap(line, inner):
                body.append(self.paint(v, tone) + ' ' + pad(part, inner) + ' ' + self.paint(v, tone))
        return [top, *body, self.paint(bl + h * (width-2) + br, tone)]

    def pair(self, left_title, left, right_title, right, min_width=72):
        if self.width < min_width:
            return self.panel(left_title, left) + self.panel(right_title, right, tone='cyan')
        lw = (self.width - 2) // 2
        rw = self.width - 2 - lw
        left = [p for line in left for p in wrap(line, lw-4)]
        right = [p for line in right for p in wrap(line, rw-4)]
        n = max(len(left), len(right))
        a = self.panel(left_title, left + [''] * (n-len(left)), lw)
        b = self.panel(right_title, right + [''] * (n-len(right)), rw, 'cyan')
        return [x + '  ' + y for x, y in zip(a,b)]

    def options(self, entries, two=True, columns=2, width=None):
        lines = [self.paint(f'[{key}]', 'gold') + ' ' + desc for key, desc in entries]
        width = width or self.width
        if two:
            for cols in range(columns, 1, -1):
                w = (width-4-2*(cols-1))//cols
                if all(cell_width(line) <= w for line in lines):
                    return ['  '.join(pad(line,w) for line in lines[i:i+cols]).rstrip()
                            for i in range(0,len(lines),cols)]
        return lines

    def screen(self, section, lines, footer='Ketik perintah lalu Enter.', subtitle=''):
        if self.clear:
            if self.ansi:
                print('\x1b[2J\x1b[H', end='')
            elif os.name == 'nt':
                os.system('cls')
        title = 'DUNGEON CHRONICLES'
        trail = ' / ' + section.upper()
        head = self.paint(title, 'gold') + self.paint(trail, 'muted') if len(title+trail) <= self.width else self.paint(title, 'gold') + '\n' + self.paint(section.upper(), 'cyan')
        print(head)
        if subtitle:
            for line in wrap(subtitle, self.width):
                print(self.paint(line, 'muted'))
        print(self.paint(('-' if self.ascii else '─') * self.width, 'muted'))
        for line in lines:
            print(line)
        if footer:
            for line in wrap(footer, self.width):
                print(self.paint(line, 'muted'))

    def ask(self, label, valid):
        while True:
            value = input(self.paint('> ', 'gold') + label + ': ').strip().upper()
            if value in valid:
                return value
            print(self.paint('Perintah tidak dikenali. Pilih: ' + ', '.join(sorted(valid)), 'red'))

    def pause(self, label='Enter untuk kembali'):
        input(self.paint('> ', 'gold') + label + ' ')
