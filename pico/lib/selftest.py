# Run at boot until there is a screen: SeedSigner's seed and wallet code against known answers.
# LAST keeps the line printed at boot, which comes before any host can attach
import gc, time
t0 = time.ticks_ms()
from seedsigner.models.seed import Seed
from seedsigner.models.settings import SettingsConstants as SC
from seedsigner.helpers import wallet
from seedsigner.helpers.bitwasm import BitwasmReview
import binascii, hashlib

# bitwasm-signer's own_mixed_nwu vector and the hash of the signed PSBT trimmed for the QR, as CPython's fork signs it
PSBT = "cHNidP8BAMUCAAAAAi3cJLA5qNmU6PAXQFY7QkDphmQ2iS3DXR4GlOZQu2gMAAAAAAD9////RXe+3a5meMIh5QyFFTp/Cs3laOFUFY+TuBbIwtGcj28BAAAAAP3///8DoIYBAAAAAAAWABSlpznvac+MBo6URWMiZxE52rh26iBOAAAAAAAAFgAUmEQgSFlZ0Noj5/6QK/MVgUzHtktovwAAAAAAACJRIIgtdOXQVy1agWzvAEGpa2wd6DL2+WdtlgXETV6al9PcAAAAAAABAFICAAAAATAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwAAAAAAD/////AaCGAQAAAAAAFgAUwM681sPTyox13F7GLr5VMw75EOIAAAAAAQEfoIYBAAAAAAAWABTAzrzWw9PKjHXcXsYuvlUzDvkQ4iIGAzDVT9DdQgpuX402JPXzSCyuNQ951fB1O/W+75wtka88GHPF2gpUAACAAAAAgAAAAIAAAAAAAAAAAAABAH0CAAAAATExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExAAAAAAD/////AugDAAAAAAAAFgAUMTExMTExMTExMTExMTExMTExMTFwEQEAAAAAACJRIKYIafDbzx3GWcnOy6+AUBNeqejNxIcFPx3GiAlJ3GhMAAAAAAEBK3ARAQAAAAAAIlEgpghp8NvPHcZZyc7Lr4BQE16p6M3EhwU/HcaICUncaEwhFsyKS8ZNiXvdxfvC9nD3qLoLOGd5EGzxIjxvxdfNb8EVGQBzxdoKVgAAgAAAAIAAAACAAAAAAAAAAAAAACICAoSuDvvlyzWyQDbUjUnTxVqE+nVVK9Fi/DoqVeKZfdRZGHPF2gpUAACAAAAAgAAAAIAAAAAABQAAAAAhBzmfGy9Dk/KaGMk3hZxd2KdzUBAxV+uIDwLowIIUJ3zvGQBzxdoKVgAAgAAAAIAAAACAAQAAAAAAAAAA"
SIGNED_SHA256 = "6f976b262aa8c3056cab31d8ac8ea54eb27bec857445ebbbb61a25b32f8d03eb"

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
    t = time.ticks_ms()
    review = BitwasmReview(binascii.a2b_base64(PSBT), seed, SC.MAINNET)
    signed = hashlib.sha256(review.sign()).digest()
    psbt_ms = time.ticks_diff(time.ticks_ms(), t)
    bad = [k for k in WANT if got[k] != WANT[k]]
    if binascii.hexlify(signed).decode() != SIGNED_SHA256:
        bad.append("psbt")
    gc.collect()
    LAST = "selftest %s import ms %d seed ms %d psbt ms %d free KB %d" % (
        "FAIL " + ", ".join(bad) if bad else "ok", IMPORT_MS, ms, psbt_ms, gc.mem_free() // 1024)
    print(LAST)
    return not bad


run()
