# micropython-lib's os (the built-in plus os.path, copied in by pico/Makefile) with walk and sep
from uos import *
from . import path

sep = "/"


def walk(top):
    try:
        entries = list(ilistdir(top))
    except OSError:
        return
    dirs = [e[0] for e in entries if e[1] == 0x4000]
    files = [e[0] for e in entries if e[1] != 0x4000]
    yield top, dirs, files
    for d in dirs:
        yield from walk(top.rstrip("/") + "/" + d)


# MicroPython has no os.fspath, so these take a pathlib.Path only once it is a str
def _str_args(f):
    return lambda *a: f(*[x if isinstance(x, (str, bytes)) else str(x) for x in a])


for _n in ("join", "exists", "isdir", "isfile", "dirname", "basename", "abspath", "split"):
    setattr(path, _n, _str_args(getattr(path, _n)))
