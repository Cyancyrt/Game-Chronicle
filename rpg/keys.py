"""Immediate arrows on Windows CMD and POSIX terminals; line fallback for redirected IO."""
import os,sys

def read_key():
    if not sys.stdin.isatty():
        return input('> ').strip().upper()
    if os.name=='nt':
        import msvcrt
        c=msvcrt.getwch()
        if c in ('\x00','\xe0'):
            return {'H':'UP','P':'DOWN','K':'LEFT','M':'RIGHT'}.get(msvcrt.getwch(),'')
        if c=='\x03': raise KeyboardInterrupt
        return c.upper()
    import termios,tty,select
    fd=sys.stdin.fileno(); old=termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd); c=os.read(fd,1)
        if c==b'\x1b':
            seq=b''
            for _ in range(2):
                if select.select([fd],[],[],.08)[0]: seq+=os.read(fd,1)
            return {b'[A':'UP',b'[B':'DOWN',b'[D':'LEFT',b'[C':'RIGHT',b'OA':'UP',b'OB':'DOWN',b'OD':'LEFT',b'OC':'RIGHT'}.get(seq,'')
        if c==b'\x04' or not c: raise EOFError
        return c.decode(errors='ignore').upper()
    finally: termios.tcsetattr(fd,termios.TCSADRAIN,old)
