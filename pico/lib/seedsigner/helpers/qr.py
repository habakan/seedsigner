# SeedSigner's QR helper on the Pico: _gfx encodes with qrcodegen and draws the modules straight onto the
# canvas when the image is pasted, so a 240x240 QR code costs no pixel buffer
from PIL import Image

try:
    import _gfx
except ImportError:  # CPython, testing
    from PIL import _gfx_sim as _gfx


class QR:
    STYLE__DEFAULT = 1
    STYLE__ROUNDED = 2
    STYLE__GRID = 3

    def __init__(self, *args, **kwargs):
        pass

    def qrimage(self, data, width=240, height=240, border=3, style=None, background_color="#444"):
        return _image(data, width, height, border, style or QR.STYLE__DEFAULT, background_color)

    def qrimage_io(self, data, width=240, height=240, border=3, background_color="808080"):
        # The Pi's qrencode path: square modules, a hex colour without "#"
        if not 1 <= border <= 10:
            border = 3
        return _image(data, width, height, border, QR.STYLE__DEFAULT, "#" + background_color.lstrip("#"))


def _image(data, width, height, border, style, background_color):
    out = Image.Image("RGBA", (width, height), None)
    bg = Image.c332(Image.rgba(background_color))
    out.ops.append(("qr", _gfx.qr_encode(data), border, 0, 0, width, height, Image.c332((0, 0, 0)), bg, style))
    return out
