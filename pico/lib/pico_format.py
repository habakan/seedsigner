# f"{x:spec}" for MicroPython, whose str.format ignores a class's __format__ (pico/lib/decimal.py's Decimal
# in BtcAmount): pico/tools/to_micropython.py turns such fields into fmt(x, "spec")


def fmt(value, spec):
    if isinstance(value, (int, float, str)) or not hasattr(value, "__format__"):
        return ("{:" + spec + "}").format(value)
    return value.__format__(spec)
