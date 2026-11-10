# The dev main.py on make -C pico sim's unix port (drive.py sim runs it): buttons typed on stdin, and a camera
# that reads only qr_inject.txt in the working directory; _gfx is micropython-pil's, drawing to no display
import sys


class Pin:
    IN, OUT, PULL_UP, PULL_DOWN = 0, 1, 2, 3

    def __init__(self, *args, **kwargs):
        pass

    def value(self, v=None):
        return 1


class machine:  # MicroPython cannot make a module object here; a class serves for "from machine import Pin"
    Pin = Pin


class _camera:
    """No sensor: every read finds no code, so camera.py's qr_inject.txt is all a scan sees."""
    _frame = bytes(240 * 240 * 2)

    def open():
        pass

    close = capture = open

    def read(budget=0):
        return None

    def frame():
        return _camera._frame

    def stats():
        return (0, 0, 0)


import _thread


class _one_thread:
    """_thread as the rp2 port has it: one thread besides the main one (core1), which threading.py relies on."""
    allocate_lock, get_ident, live = _thread.allocate_lock, _thread.get_ident, False

    def start_new_thread(f, args):
        if _one_thread.live:
            raise OSError(16)
        _one_thread.live = True

        def run():
            try:
                f(*args)
            finally:
                _one_thread.live = False
        _thread.start_new_thread(run, ())


sys.modules["machine"], sys.modules["_camera"], sys.modules["_thread"] = machine, _camera, _one_thread
import pico_boot
import RPi.GPIO
RPi.GPIO.serial_keys = True
RPi.GPIO.MAIN_IDENT = _thread.get_ident()  # 1 only on the rp2 port
from seedsigner.controller import Controller
c = Controller.get_instance()
c.screensaver_activation_ms = 1 << 30  # reading a long signed PSBT off the screen outlasts its two minutes
c.start()
