"""
SeedSigner's own MainMenuScreen through the Pico's PIL shim, on CPython: saves what the framebuffer holds
and how far it is from real PIL's picture of the same screen, both in the framebuffer's palette.

    python3 pico/tests/render_screen.py build/pico/fonts out.png
"""
import importlib.util, pathlib, sys, types
from unittest.mock import MagicMock

root = pathlib.Path(__file__).resolve().parents[2]
from PIL import Image as RealImage  # the real one, for the comparison, before the shim takes "PIL"

# The shim as "PIL", the simulated _gfx, the bitmap fonts
shim = types.ModuleType("PIL")
shim.__path__ = [str(root / "pico/lib/PIL")]
real_pil = {k: v for k, v in sys.modules.items() if k == "PIL" or k.startswith("PIL.")}
for k in real_pil:
    del sys.modules[k]
sys.modules["PIL"] = shim
sys.path.insert(0, str(root / "pico/tests"))
sys.path.insert(0, sys.argv[1])
import gfx_sim
sys.modules["_gfx"] = gfx_sim
sys.modules["RPi"] = MagicMock()
sys.modules["RPi.GPIO"] = MagicMock()
sys.path.insert(0, str(root / "src"))
spec = importlib.util.spec_from_file_location("seedsigner.hardware.displays.ST7789", root / "pico/lib/seedsigner/hardware/displays/ST7789.py")
drv = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = drv
spec.loader.exec_module(drv)

from seedsigner.gui.renderer import Renderer
from seedsigner.gui.screens.screen import MainMenuScreen, ButtonOption
from seedsigner.gui.components import SeedSignerIconConstants
from seedsigner.views.view import MainMenuView

Renderer.configure_instance()
r = Renderer.get_instance()
which = sys.argv[3] if len(sys.argv) > 3 else "main"
if which == "main":
    buttons = [MainMenuView.SCAN, MainMenuView.SEEDS, MainMenuView.TOOLS, MainMenuView.SETTINGS]
    screen = MainMenuScreen(title="Home", button_data=buttons, show_back_button=False, show_power_button=True)
else:  # small supersampled body text
    from seedsigner.gui.screens.screen import WarningScreen
    screen = WarningScreen(title="Caution", status_headline="Privacy Leak!",
                           text="Xpub can be used to view all future transactions.", button_data=[ButtonOption("I Understand")])
screen._render()
r.show_image()
ours = gfx_sim.to_rgb()
open(sys.argv[2] + ".bin", "wb").write(gfx_sim.canvas_bytes)

for k in list(sys.modules):
    if k == "PIL" or k.startswith("PIL."):
        del sys.modules[k]
sys.modules.update(real_pil)
RealImage.frombytes("RGB", (240, 240), ours).save(sys.argv[2])
ref = root / ("seedsigner-screenshots/en/main_menu_views/MainMenuView.png" if which == "main" else "none")
if ref.exists():
    want = RealImage.open(ref).convert("RGB").tobytes()
    want = b"".join(bytes(gfx_sim.RGB[gfx_sim.colour(want[i], want[i + 1], want[i + 2])]) for i in range(0, len(want), 3))
    diff = sum(1 for i in range(0, len(want), 3) if max(abs(ours[i + j] - want[i + j]) for j in range(3)) > 40)
    print("pixels differing from real PIL's (quantized):", diff, "of", 240 * 240)
print("shows", gfx_sim.shows)
