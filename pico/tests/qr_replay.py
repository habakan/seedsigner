# Decode every QR session the test suite recorded (SEEDSIGNER_RECORD_QR) and print what DecodeQR says;
# CPython and MicroPython must print the same. Reads qr_sessions.json, a session a line, from the working
# directory in 4 KB reads: over a USB mount small reads are slow, and the whole file does not fit the heap
import binascii, hashlib, json
from seedsigner.models.decode_qr import DecodeQR


def sessions():
    with open("qr_sessions.json") as f:
        buf = ""
        while True:
            chunk = f.read(4096)
            lines = (buf + chunk).split("\n")
            buf = lines.pop()
            for line in lines:
                if line:
                    yield json.loads(line)
            if not chunk:
                return


for n, s in enumerate(sessions()):
    d = DecodeQR(wordlist_language_code=s["lang"])
    statuses = []
    for kind, value in s["data"]:
        try:
            statuses.append(int(d.add_data(binascii.a2b_base64(value) if kind == "b" else value)))
        except Exception as e:
            statuses.append("raise")
    out = [n, statuses, d.qr_type, d.is_complete, d.is_invalid]
    for flag in ("is_psbt", "is_seed", "is_address", "is_sign_message", "is_settings", "is_wallet_descriptor"):
        try:
            out.append(getattr(d, flag))
        except Exception:
            out.append("raise")
    if d.is_complete and d.is_psbt:
        raw = d.get_data_psbt()
        out.append(binascii.hexlify(hashlib.sha256(bytes(raw)).digest()).decode() if raw else None)
    elif d.is_complete and d.is_seed:
        out.append(" ".join(d.get_seed_phrase() or []))
    elif d.is_complete and d.is_address:
        out.append((d.get_address(), d.get_address_type()))
    elif d.is_complete and d.is_settings:
        out.append(d.get_settings_data())
    print(out)
