# Run at boot until there is a screen: SeedSigner's seed and wallet code against known answers.
# LAST keeps the line printed at boot, which comes before any host can attach
import gc, time
t0 = time.ticks_ms()
from seedsigner.models.seed import Seed
from seedsigner.models.settings import SettingsConstants as SC
from seedsigner.helpers import wallet

WANT = {
    "fingerprint": "73c5da0a",
    "address": "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu",
    "taproot change": "bc1p3qkhfews2uk44qtvauqyr2ttdsw7svhkl9nkm9s9c3x4ax5h60wqwruhk7",
}


LAST = None
IMPORT_MS = time.ticks_diff(time.ticks_ms(), t0)


def run():
    global LAST
    t = time.ticks_ms()
    seed = Seed(("abandon " * 11 + "about").split())
    ms = time.ticks_diff(time.ticks_ms(), t)
    got = {
        "fingerprint": seed.get_fingerprint(),
        "address": wallet.address(seed, "m/84h/0h/0h", SC.MAINNET, False, 0),
        "taproot change": wallet.address(seed, "m/86h/0h/0h", SC.MAINNET, True, 0),
    }
    bad = [k for k in WANT if got[k] != WANT[k]]
    gc.collect()
    LAST = "selftest %s import ms %d seed ms %d free KB %d" % (
        "FAIL " + ", ".join(bad) if bad else "ok", IMPORT_MS, ms, gc.mem_free() // 1024)
    print(LAST)
    return not bad


run()
