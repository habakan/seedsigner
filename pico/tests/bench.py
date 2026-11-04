# Time and heap of SeedSigner's seed and wallet code on the device
import gc, time
gc.collect()
free0 = gc.mem_free()
t = time.ticks_ms()
from seedsigner.models.seed import Seed
from seedsigner.models.settings import SettingsConstants as SC
from seedsigner.helpers import wallet
gc.collect()
print("import ms", time.ticks_diff(time.ticks_ms(), t), "heap KB", (free0 - gc.mem_free()) // 1024)


def timed(label, f):
    t = time.ticks_us()
    r = f()
    print(label, "ms", time.ticks_diff(time.ticks_us(), t) // 1000)
    return r


seed = timed("seed (PBKDF2)", lambda: Seed(("abandon " * 11 + "about").split()))
timed("xpub", lambda: wallet.account_xpub(seed, "m/84h/0h/0h", SC.MAINNET))
timed("address", lambda: wallet.address(seed, "m/84h/0h/0h", SC.MAINNET, False, 0))
timed("10 addresses", lambda: [wallet.address(seed, "m/84h/0h/0h", SC.MAINNET, False, i) for i in range(10)])
timed("message", lambda: wallet.sign_message(seed, "m/84h/0h/0h/0/0", SC.MAINNET, b"hello"))
gc.collect()
print("heap KB after", (free0 - gc.mem_free()) // 1024, "free KB", gc.mem_free() // 1024)
