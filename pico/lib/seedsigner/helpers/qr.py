# SeedSigner's QR helper on the Pico, for now only importable: QR display will draw with qrcodegen in C
class QR:
    STYLE__DEFAULT = 1
    STYLE__ROUNDED = 2
    STYLE__GRID = 3

    def __init__(self, *args, **kwargs):
        pass

    def qrimage(self, *args, **kwargs):
        raise NotImplementedError("QR display is not on the Pico yet")

    def qrimage_io(self, *args, **kwargs):
        raise NotImplementedError("QR display is not on the Pico yet")
