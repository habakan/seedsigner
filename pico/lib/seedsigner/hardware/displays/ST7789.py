"""SeedSigner's ST7789 on the Pico: an image's drawing (pico/lib/PIL/Image.py) is replayed into _gfx's band
of rows, one band at a time, each sent to the LCD as it is done."""
from PIL import Image, ImageDraw
from seedsigner.hardware.displays.display_driver import BaseDisplayDriver

_gfx = Image._gfx


def render(ops, x, y, size, each, region=None):
    """Draws `ops` at (x, y) over a size[0] x size[1] box on the screen, or only `region` of it (inclusive),
    band by band, calling each(x0, y0, x1, y1) with what each band holds."""
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(_gfx.WIDTH, x + size[0]), min(_gfx.HEIGHT, y + size[1])
    if region:
        x0, y0 = max(x0, x + region[0]), max(y0, y + region[1])
        x1, y1 = min(x1, x + region[2] + 1), min(y1, y + region[3] + 1)
    for by in range(y0, y1, _gfx.BAND):
        by1 = min(y1, by + _gfx.band(by))
        _gfx.fill(x0, by, x1, by1, 0)
        ImageDraw.replay(ops, x, y, (x0, by, x1, by1))
        each(x0, by, x1, by1)


class ST7789(BaseDisplayDriver):
    last = None
    shown = None  # the image the screen holds all of, so showing it again sends only what changed

    def show_image(self, image, x_start=0, y_start=0):
        whole = (x_start, y_start) == (0, 0) and image.size == (_gfx.WIDTH, _gfx.HEIGHT)
        region = image.dirty if whole and image is ST7789.shown else None
        if whole and image is ST7789.shown and region is None:
            return  # nothing drawn since
        ST7789.last = (image.snapshot(), x_start, y_start, image.size)
        render(*ST7789.last, _gfx.show, region)
        image.dirty = None
        ST7789.shown = image if whole else None


def screenshot(out):
    """Calls out() with what the screen was last sent, a row at a time in _gfx.save's run-length encoding,
    for pico/tests/drive.py: a row's bytes find room in a fragmented heap."""
    import gc
    from seedsigner.gui.renderer import Renderer

    def rows(x0, y0, x1, y1):
        for y in range(y0, y1):
            out(_gfx.save(x0, y, x1, y + 1))

    gc.collect()
    with Renderer.get_instance().lock:  # the band is shared with a screen's or a toast's thread
        if ST7789.last:
            render(*ST7789.last, rows)
