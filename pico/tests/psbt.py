# Review and sign a PSBT as SeedSigner's bitwasm helper does: parser.wasm, then the signer. The PSBT is
# bitwasm-signer's own_mixed_nwu vector (P2WPKH and P2TR inputs of BIP39's test seed), mainnet
import binascii, hashlib, time
from seedsigner.models.seed import Seed
from seedsigner.models.settings import SettingsConstants as SC
from seedsigner.helpers.bitwasm import BitwasmReview

PSBT = binascii.a2b_base64("cHNidP8BAMUCAAAAAi3cJLA5qNmU6PAXQFY7QkDphmQ2iS3DXR4GlOZQu2gMAAAAAAD9////RXe+3a5meMIh5QyFFTp/Cs3laOFUFY+TuBbIwtGcj28BAAAAAP3///8DoIYBAAAAAAAWABSlpznvac+MBo6URWMiZxE52rh26iBOAAAAAAAAFgAUmEQgSFlZ0Noj5/6QK/MVgUzHtktovwAAAAAAACJRIIgtdOXQVy1agWzvAEGpa2wd6DL2+WdtlgXETV6al9PcAAAAAAABAFICAAAAATAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwAAAAAAD/////AaCGAQAAAAAAFgAUwM681sPTyox13F7GLr5VMw75EOIAAAAAAQEfoIYBAAAAAAAWABTAzrzWw9PKjHXcXsYuvlUzDvkQ4iIGAzDVT9DdQgpuX402JPXzSCyuNQ951fB1O/W+75wtka88GHPF2gpUAACAAAAAgAAAAIAAAAAAAAAAAAABAH0CAAAAATExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExAAAAAAD/////AugDAAAAAAAAFgAUMTExMTExMTExMTExMTExMTExMTFwEQEAAAAAACJRIKYIafDbzx3GWcnOy6+AUBNeqejNxIcFPx3GiAlJ3GhMAAAAAAEBK3ARAQAAAAAAIlEgpghp8NvPHcZZyc7Lr4BQE16p6M3EhwU/HcaICUncaEwhFsyKS8ZNiXvdxfvC9nD3qLoLOGd5EGzxIjxvxdfNb8EVGQBzxdoKVgAAgAAAAIAAAACAAAAAAAAAAAAAACICAoSuDvvlyzWyQDbUjUnTxVqE+nVVK9Fi/DoqVeKZfdRZGHPF2gpUAACAAAAAgAAAAIAAAAAABQAAAAAhBzmfGy9Dk/KaGMk3hZxd2KdzUBAxV+uIDwLowIIUJ3zvGQBzxdoKVgAAgAAAAIAAAACAAQAAAAAAAAAA")

seed = Seed(("abandon " * 11 + "about").split())
t = time.ticks_ms() if hasattr(time, "ticks_ms") else None
review = BitwasmReview(PSBT, seed, SC.MAINNET)
d = review.display
print("fee", d["fee"], "spend", d["spend"])
for o in d["outputs"]:
    print("out", o["amount"], o["owner"], o["text"])
signed = review.sign()
print("signed", len(signed), binascii.hexlify(hashlib.sha256(signed).digest()).decode())
if t is not None:
    print("review and sign ms", time.ticks_diff(time.ticks_ms(), t))
