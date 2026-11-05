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


def input(channel):
    return _pins[channel].value()


def output(channel, value):
    _pins[channel].value(value)


def cleanup(*args):
    pass
