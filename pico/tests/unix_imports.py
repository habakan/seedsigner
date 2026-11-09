# Imports SeedSigner's controller and every view on MicroPython's unix port, as the device would
import sys
sys.path.insert(0, "pico/third_party/micropython-pil/PIL")
import _gfx_sim as gfx_sim
sys.modules["_gfx"] = gfx_sim


class Pin:
    IN, OUT, PULL_UP, PULL_DOWN = 0, 1, 2, 3

    def __init__(self, *args, **kwargs):
        pass

    def value(self, v=None):
        return 1


class machine:
    Pin = Pin


sys.modules["machine"] = machine
for m in ("seedsigner.controller", "seedsigner.views.view", "seedsigner.views.seed_views", "seedsigner.views.psbt_views",
          "seedsigner.views.scan_views", "seedsigner.views.settings_views", "seedsigner.views.tools_views"):
    __import__(m)
    print("ok", m)
