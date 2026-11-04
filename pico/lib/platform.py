def system():
    return "MicroPython"


def machine():
    return "rp2"


def uname():
    # (system, node, release, version, machine); SeedSigner reads the node name only
    return ("MicroPython", "seedsigner-pico", "", "", "rp2")
