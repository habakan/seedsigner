# MicroPython's time, extended with CPython's fractional time(): whole seconds made buttons.py's
# int(time.time() * 1000) step by 1000, so the same key twice within a second was taken for one held
from utime import *  # noqa: F401,F403  (the built-in, under its other name)
from utime import time_ns as _ns


def time():
    return _ns() / 1e9
