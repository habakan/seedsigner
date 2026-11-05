# What the Pico changes in SeedSigner as it starts, rather than in SeedSigner's source; main.py imports it
# before the Controller (pico/Makefile's device-install)
import seedsigner.controller as controller
from seedsigner.models.decode_qr import DecodeQR


def _preload(self):
    # The seed storage alone: the heap cannot hold every view's module at once, and each loads when first used
    from seedsigner.models.seed_storage import SeedStorage
    controller.Controller.get_instance()._storage = SeedStorage()


controller.BackgroundImportThread.run = _preload

_extract_qr_data = DecodeQR.extract_qr_data


def _bytes_or_frame(image, is_binary=False):
    # The Pico's camera reads the QR code itself (pico/lib/seedsigner/hardware/camera.py) and hands over its bytes
    from seedsigner.hardware.camera import NO_CODE
    if image is NO_CODE:
        return None
    if isinstance(image, (bytes, bytearray)):
        return bytes(image)
    return _extract_qr_data(image, is_binary)


DecodeQR.extract_qr_data = staticmethod(_bytes_or_frame)

from seedsigner.gui.screens.scan_screens import ScanScreen

_scan_post_init = ScanScreen.__post_init__


def _scan_without_preview_thread(self):
    # Drawn between camera reads (ScanScreen._run) instead: a read holds the GIL for seconds, and core1's
    # thread waiting on it left the screen black
    _scan_post_init(self)
    self.threads.remove(self.preview)


ScanScreen.__post_init__ = _scan_without_preview_thread
