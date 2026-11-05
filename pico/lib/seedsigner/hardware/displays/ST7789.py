"""SeedSigner's ST7789 on the Pico: the canvas becomes _gfx's framebuffer (pico/lib/PIL/Image.py)."""
from PIL import Image, ImageDraw
from seedsigner.hardware.displays.display_driver import BaseDisplayDriver

_gfx = Image._gfx


class ST7789(BaseDisplayDriver):
    canvas = None

    def show_image(self, image, x_start=0, y_start=0):
        if ST7789.canvas is None and image.size == (_gfx.WIDTH, _gfx.HEIGHT):
            image.bind()  # the Renderer's canvas, the first image it shows
            ST7789.canvas = image
        elif image is not ST7789.canvas:
            ImageDraw.replay(image.snapshot(), x_start, y_start, (0, 0, _gfx.WIDTH, _gfx.HEIGHT))
        _gfx.show()
