# RPi.GPIO as SeedSigner's buttons use it, on the Pico. The Pi's header pins (BOARD numbering) map to
# bitwasm-signer-pico's board_pins.h: the joystick and KEY1-3 where a Pi HAT has them
from machine import Pin

BOARD, BCM = 10, 11
IN, OUT = 1, 0
PUD_UP, PUD_DOWN, PUD_OFF = 22, 21, 20
LOW, HIGH = 0, 1
RPI_INFO = {"P1_REVISION": 3}

BOARD_TO_GP = {
    31: 13,  # KEY_UP
    35: 17,  # KEY_DOWN, the current build's NEXT
    29: 20,  # KEY_LEFT
    37: 22,  # KEY_RIGHT
    33: 26,  # KEY_PRESS, the current build's SELECT
    40: 27,  # KEY1
    38: 28,  # KEY2
    36: 1,   # KEY3
}

_pins = {}


def setmode(mode):
    if mode != BOARD:
        raise ValueError("only BOARD numbering is mapped")


def setwarnings(flag):
    pass


def setup(channel, direction, pull_up_down=PUD_OFF, initial=None):
    gp = BOARD_TO_GP[channel]
    if direction == IN:
        pull = Pin.PULL_UP if pull_up_down == PUD_UP else Pin.PULL_DOWN if pull_up_down == PUD_DOWN else None
        _pins[channel] = Pin(gp, Pin.IN, pull)
    else:
        _pins[channel] = Pin(gp, Pin.OUT, value=initial or 0)


# Development only (make device-install-dev): keys typed over USB serial press buttons, and "s" prints the
# framebuffer, so a flow can be driven and watched from a computer. Off, a signer takes no USB input
serial_keys = False
SERIAL_KEYS = {"u": 31, "d": 35, "l": 29, "r": 37, "p": 33, "1": 40, "2": 38, "3": 36}
_poll, _pressed, _until, _queue = None, None, 0, []
# Only core0's main thread (ident 1 on the rp2 port) reads them: a toast's thread on core1 also reads the
# buttons, and holds the screen's lock that a screenshot takes
MAIN_IDENT = 1


def _serial(channel):
    """True while a typed key holds `channel` down: 100 ms down, then 200 ms up, so the same key twice is two
    presses to buttons.py, which repeats a key held past 225 ms and calls one 250 ms apart a new press."""
    global _poll, _pressed, _until
    import _thread, sys, time
    if _thread.get_ident() != MAIN_IDENT:
        return _pressed == channel
    if _poll is None:
        import select
        _poll = select.poll()
        _poll.register(sys.stdin, select.POLLIN)
    while _poll.poll(0):
        ch = sys.stdin.read(1)
        if ch == "s":
            import binascii
            from seedsigner.hardware.displays.ST7789 import screenshot
            import gc
            gc.collect()
            print("free", gc.mem_free())  # the heap, after the screen just drawn
            print("<<FB")
            screenshot(lambda part: print(binascii.b2a_base64(part, newline=False).decode()))
            print("FB>>")
        elif ch in SERIAL_KEYS:
            _queue.append(SERIAL_KEYS[ch])
    now = time.ticks_ms()
    if _pressed is not None and time.ticks_diff(now, _until) >= 0:
        _pressed, _until = None, time.ticks_add(now, 200)
    if _pressed is None and _queue and time.ticks_diff(now, _until) >= 0:
        _pressed, _until = _queue.pop(0), time.ticks_add(now, 100)
    return _pressed == channel


def input(channel):
    if serial_keys and _serial(channel):
        return LOW
    return _pins[channel].value()


def output(channel, value):
    _pins[channel].value(value)


def cleanup(*args):
    pass
