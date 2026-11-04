# What SeedSigner's PSBT views read, from WasmPSBTParser (parser.wasm, then the signer), and the signing. The PSBT is
# bitwasm-signer's own_mixed_nwu vector (P2WPKH and P2TR inputs of BIP39's test seed), mainnet
import binascii, hashlib, time
from seedsigner.models.seed import Seed
from seedsigner.models.settings import SettingsConstants as SC
from seedsigner.helpers.wallet import path_to_str
from seedsigner.models.psbt_wasm import WasmPSBTParser

PSBT = binascii.a2b_base64("cHNidP8BAMUCAAAAAi3cJLA5qNmU6PAXQFY7QkDphmQ2iS3DXR4GlOZQu2gMAAAAAAD9////RXe+3a5meMIh5QyFFTp/Cs3laOFUFY+TuBbIwtGcj28BAAAAAP3///8DoIYBAAAAAAAWABSlpznvac+MBo6URWMiZxE52rh26iBOAAAAAAAAFgAUmEQgSFlZ0Noj5/6QK/MVgUzHtktovwAAAAAAACJRIIgtdOXQVy1agWzvAEGpa2wd6DL2+WdtlgXETV6al9PcAAAAAAABAFICAAAAATAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwAAAAAAD/////AaCGAQAAAAAAFgAUwM681sPTyox13F7GLr5VMw75EOIAAAAAAQEfoIYBAAAAAAAWABTAzrzWw9PKjHXcXsYuvlUzDvkQ4iIGAzDVT9DdQgpuX402JPXzSCyuNQ951fB1O/W+75wtka88GHPF2gpUAACAAAAAgAAAAIAAAAAAAAAAAAABAH0CAAAAATExMTExMTExMTExMTExMTExMTExMTExMTExMTExMTExAAAAAAD/////AugDAAAAAAAAFgAUMTExMTExMTExMTExMTExMTExMTFwEQEAAAAAACJRIKYIafDbzx3GWcnOy6+AUBNeqejNxIcFPx3GiAlJ3GhMAAAAAAEBK3ARAQAAAAAAIlEgpghp8NvPHcZZyc7Lr4BQE16p6M3EhwU/HcaICUncaEwhFsyKS8ZNiXvdxfvC9nD3qLoLOGd5EGzxIjxvxdfNb8EVGQBzxdoKVgAAgAAAAIAAAACAAAAAAAAAAAAAACICAoSuDvvlyzWyQDbUjUnTxVqE+nVVK9Fi/DoqVeKZfdRZGHPF2gpUAACAAAAAgAAAAIAAAAAABQAAAAAhBzmfGy9Dk/KaGMk3hZxd2KdzUBAxV+uIDwLowIIUJ3zvGQBzxdoKVgAAgAAAAIAAAACAAQAAAAAAAAAA")

seed = Seed(("abandon " * 11 + "about").split())
t = time.ticks_ms() if hasattr(time, "ticks_ms") else None
p = WasmPSBTParser(PSBT, seed, SC.MAINNET)
print("spend", p.spend_amount, "change", p.change_amount, "fee", p.fee_amount, "inputs", p.num_inputs, "policy", p.policy)
print("destinations", p.destination_addresses, p.destination_amounts, "high fee", p.is_high_fee)
for c in p.change_data:
    print("change", c["output_index"], c["address"], c["amount"], path_to_str(c["verified_derivation_path"]))
signed = p.bitwasm_review.sign()
print("signed", len(signed), binascii.hexlify(hashlib.sha256(signed).digest()).decode())
if t is not None:
    print("parse and sign ms", time.ticks_diff(time.ticks_ms(), t))
