# Scan with the camera into SeedSigner's DecodeQR; a PSBT is then reviewed and signed with BIP39's test
# seed through WasmPSBTParser, as the views would. Show the QR within 60 s of starting
import binascii, gc, hashlib, time, _camera
from seedsigner.models.decode_qr import DecodeQR
from seedsigner.models.qr_type import QRType

d = DecodeQR()
_camera.open()
start, frames, reads = time.ticks_ms(), 0, 0
try:
    while not d.is_complete and time.ticks_diff(time.ticks_ms(), start) < 60000:
        r = _camera.read(2 if d.qr_type == QRType.PSBT__UR2 else 0)
        frames += 1
        if isinstance(r, bytes):
            reads += 1
            d.add_data(r)
            print("frame", frames, d.qr_type, d.get_percent_complete(), "%")
            if d.is_invalid:
                break
finally:
    _camera.close()
secs = time.ticks_diff(time.ticks_ms(), start) / 1000
print("scan", "complete" if d.is_complete else "incomplete", d.qr_type, "frames", frames, "read", reads, "s", secs)

if d.is_complete and d.is_psbt:
    from seedsigner.models.seed import Seed
    from seedsigner.models.settings import SettingsConstants as SC
    from seedsigner.models.psbt_wasm import WasmPSBTParser
    gc.collect()
    p = WasmPSBTParser(d.get_psbt(), Seed(("abandon " * 11 + "about").split()), SC.MAINNET)
    print("spend", p.spend_amount, "change", p.change_amount, "fee", p.fee_amount, "to", p.destination_addresses)
    signed = p.bitwasm_review.sign()
    print("signed", len(signed), binascii.hexlify(hashlib.sha256(signed).digest()).decode())
elif d.is_complete and d.is_seed:
    print("seed", " ".join(d.get_seed_phrase()))
