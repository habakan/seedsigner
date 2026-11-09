# pico/tests/screen.py on MicroPython's unix port: gfx_sim for _gfx and a Pin that is never pressed
import sys, time
sys.path.insert(0, "pico/third_party/micropython-pil/PIL")
import _gfx_sim as gfx_sim
sys.modules["_gfx"] = gfx_sim


class Pin:
    IN, OUT, PULL_UP, PULL_DOWN = 0, 1, 2, 3

    def __init__(self, *args, **kwargs):
        pass

    def value(self, v=None):
        return 1


class machine:  # MicroPython cannot make a module object here; a class serves for "from machine import Pin"
    Pin = Pin


sys.modules["machine"] = machine
exec(open("pico/tests/screen.py").read())
print("shows", gfx_sim.shows, "inked pixels", sum(1 for v in gfx_sim.canvas_bytes if v))
open("build/pico/mm_mpy.bin", "wb").write(gfx_sim.canvas_bytes)
