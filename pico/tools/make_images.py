"""
SeedSigner's images (resources/img) as the framebuffer's palette indices, one module of bytes each, for
pico/lib/PIL/Image.py's open(). load_image converts to RGB, so alpha is dropped here too.

    python3 pico/tools/make_images.py OUT_DIR IMG_DIR
"""
import pathlib
import sys

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tests"))
from gfx_sim import colour

out, src = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
(out / "__init__.py").write_text("")
for p in sorted(src.rglob("*.png")):
    img = Image.open(p).convert("RGB")
    px = img.tobytes()
    idx = bytes(colour(px[i], px[i + 1], px[i + 2]) for i in range(0, len(px), 3))
    name = "i_" + "_".join(p.relative_to(src).with_suffix("").parts).replace("-", "_")
    (out / (name + ".py")).write_text("W = %d\nH = %d\nPIXELS = %r\n" % (img.width, img.height, idx))
    print(name, img.size)
