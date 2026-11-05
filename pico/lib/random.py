# random as SeedSigner uses it: MicroPython's built-in, which this module extends, plus shuffle (the backup
# test's word buttons)
from urandom import *  # noqa: F401,F403  (the built-in, under its other name)


def shuffle(x):
    for i in range(len(x) - 1, 0, -1):
        j = randrange(i + 1)
        x[i], x[j] = x[j], x[i]
