"""
Scans, reviews and signs psbt_cases.py's PSBTs on the device through SeedSigner's own screens, with the dev main.py
(make device-install-dev), printing the heap after each screen. The camera reads qr_inject.txt instead
(pico/lib/seedsigner/hardware/camera.py): each PSBT's UR frames, then the test seed's SeedQR. The signed PSBT is
compared with what this fork signs on this machine (BITWASM_SIGNER_LIBIWASM as for pytest), and with what upstream
SeedSigner signs and trims, from git at UPSTREAM. P2TR differs from upstream by design: the signature stays tap_key_sig.

    .venv/bin/python pico/tests/psbt_flow.py PORT CASES.json [NAME...] [--reset CMD] [--upstream REF]

--reset CMD runs before each PSBT, a shell command resetting the device, as openocd writing its watchdog
(mww 0x400d8000 0x80000000): a soft reboot leaves WAMR's pool and the native signer as they were.
"""
import argparse, base64, binascii, json, os, pathlib, re, subprocess, sys, time

R = pathlib.Path(__file__).resolve().parents[2]
OUT = R / "build/pico/psbt_flow"
SOCK = "build/pico/d.sock"  # relative: a Unix socket's path is short
DRIVE = [sys.executable, str(R / "pico/tests/drive.py")]
SEEDQR = "0000" * 11 + "0003"  # abandon x11 about, Standard SeedQR
SIGNED = """import binascii
from seedsigner.controller import Controller
p = Controller.get_instance().psbt
p = memoryview(p if isinstance(p, (bytes, bytearray, memoryview)) else p.serialize())
for i in range(0, len(p), 570):  # a few hundred bytes at a time: the heap has no hole for all of a 2.5 KB PSBT in base64
    print("B64", binascii.b2a_base64(p[i:i + 570], newline=False).decode())
"""


def frames(raw):
    sys.path.insert(0, str(R / "src"))
    from seedsigner.helpers.ur2.ur_encoder import UREncoder
    from seedsigner.helpers.ur2.ur import UR
    from urtypes.crypto import PSBT
    enc = UREncoder(UR("crypto-psbt", PSBT(raw).to_cbor()), max_fragment_len=100)
    # the pure parts, then as many mixed ones as a wallet keeps looping, for any frame the scan misses
    return [enc.next_part().upper() for _ in range(2 * enc.fountain_encoder.seq_len())]


def put(port, name, text):
    """text into the device's file name, through the raw REPL in 4 KB scripts: it compiles each on the heap."""
    return repl(port, [f"f = open({name!r}, {'wa'[k > 0]!r})\nf.write({text[i:i + 4000]!r})\nf.close()\n"
                       f"import os\nprint(os.stat({name!r})[6])\n" for k, i in enumerate(range(0, len(text), 4000))])


def remove(port, name):
    """Removes the device's file name: a qr_inject.txt left behind stands in for the camera in a later, manual scan."""
    return repl(port, [f"import os\ntry:\n os.remove({name!r})\nexcept OSError:\n pass\nprint('removed')\n"], reboot=True)


def repl(port, scripts, reboot=False):
    """Runs each script at the raw REPL, which stops main.py, and returns the last one's output; reboot starts it again."""
    import serial
    s = serial.Serial(port, 115200, timeout=0.1, write_timeout=5)
    s.write(b"\r\x03\x03"); time.sleep(0.6); s.read(100000)
    s.write(b"\x01"); time.sleep(0.4); s.read(100000)
    for code in scripts:
        for j in range(0, len(code), 256):  # paced: the USB serial drops what it cannot take
            s.write(code[j:j + 256].encode()); time.sleep(0.02)
        s.write(b"\x04")
        buf, end = b"", time.time() + 30
        while buf.count(b"\x04") < 2 and time.time() < end:
            buf += s.read(4096)
    s.write(b"\x02")
    if reboot:
        time.sleep(0.3); s.write(b"\x04")  # a soft reboot, from the friendly REPL
    s.close()
    return buf.split(b"OK", 1)[-1].split(b"\x04")[0].strip().decode(errors="replace")


def share(png, test):
    from PIL import Image
    px = list(Image.open(png).convert("RGB").getdata())
    return sum(1 for p in px if test(*p)) / len(px)


def upstream_signed(raw, ref):
    """Upstream's PSBTParser.trim of the PSBT embit signs with the test seed's root."""
    src = subprocess.run(["git", "show", f"{ref}:src/seedsigner/models/psbt_parser.py"], cwd=R, capture_output=True, text=True, check=True).stdout
    (OUT / "up_psbt_parser.py").write_text(src)
    sys.path.insert(0, str(OUT)); sys.path.insert(0, str(R / "src"))
    import up_psbt_parser
    from embit import bip32, bip39
    from embit.psbt import PSBT
    p = PSBT.parse(raw)
    p.sign_with(bip32.HDKey.from_seed(bip39.mnemonic_to_seed("abandon " * 11 + "about")))
    return up_psbt_parser.PSBTParser.trim(p).serialize()


def fork_signed(raw):
    sys.path.insert(0, str(R / "src"))
    from seedsigner.models.seed import Seed
    from seedsigner.models.settings import SettingsConstants
    from seedsigner.models.psbt_wasm import WasmPSBTParser
    seed = Seed(("abandon " * 11 + "about").split())
    return bytes(WasmPSBTParser(raw, seed, SettingsConstants.MAINNET).bitwasm_review.sign())


def screen_qr(shot, secs=300):
    """The signed PSBT off the screen's animated QR, from screenshots until its UR decodes."""
    from PIL import Image
    from pyzbar.pyzbar import decode
    from seedsigner.helpers.ur2.ur_decoder import URDecoder
    from urtypes.crypto import PSBT
    dec, end = URDecoder(), time.time() + secs
    while not dec.is_complete() and time.time() < end:
        for d in decode(Image.open(shot()).convert("L").resize((960, 960), Image.NEAREST)):
            dec.receive_part(d.data.decode().lower())
    return PSBT.from_cbor(dec.result_message().cbor).data if dec.is_complete() else None


def run(port, name, raw, reset, network=None, from_screen=False):
    lines = frames(raw)
    text = "\n".join(lines + ["---", SEEDQR, "---"]) + "\n"
    if reset:
        subprocess.run(reset, shell=True, capture_output=True, timeout=60)
        time.sleep(25)  # main.py's boot: the raw REPL needs it running
    if put(port, "qr_inject.txt", text) != str(len(text)):
        sys.exit("qr_inject.txt did not reach the device")
    conf = json.dumps({"network": network} if network else {})  # read as main.py starts
    if put(port, "settings.json", conf) != str(len(conf)):
        sys.exit("settings.json did not reach the device")
    log = OUT / f"{name}.log"
    log.write_bytes(b"")
    serve = subprocess.Popen(DRIVE + ["serve", port, SOCK, str(log)], cwd=R, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(30)  # main.py's boot
        seen = [0]

        def step(keys, label, wait):
            png = OUT / f"{name}_{label}.png"
            subprocess.run(DRIVE + ["send", SOCK, keys], cwd=R, capture_output=True)
            time.sleep(wait)
            subprocess.run(DRIVE + ["send", SOCK, "", str(png)], cwd=R, capture_output=True)
            text = log.read_bytes().decode(errors="replace").replace("\r", "")
            tail, seen[0] = text[seen[0]:], len(text)
            largest = re.findall(r"max free sz: (\d+)", text)  # in 16-byte blocks
            free = re.findall(r"^free (\d+) wamr \((-?\d+), (-?\d+), (-?\d+)\)", text, re.M)
            free = free[-1] if free else ("?",) * 4
            notes = ("  ERROR" if 'File "main.py"' in tail and "KeyboardInterrupt" not in tail else "") + \
                    ("  (MemoryError in a thread)" if "Unhandled exception in thread" in tail and "MemoryError" in tail else "")
            print(f"  {label:10s} free {free[0]:>7} largest {int(largest[-1]) * 16 if largest else '?':>6} wamr peak {free[3]:>7}{notes}")
            return png, bool(notes.startswith("  ERROR"))

        from PIL import Image, ImageChops
        home, _ = step("", "home", 2)
        for t in range(3):  # a press lost: still the home screen
            png, _ = step("p", "scan", 5)
            if ImageChops.difference(Image.open(home).convert("L"), Image.open(png).convert("L")).getbbox():
                break
        for _ in lines:  # the scan screen's green progress bar
            png, _ = step("", "scanning", 10)
            if share(png, lambda r, g, b: g > 180 and r < 80 and b < 80) < 0.005:
                break
        step("p", "seed", 10)
        step("p", "overview", 15)
        for i in range(1, 15):
            png, bad = step("p", f"s{i}", 6)
            # the signed QR: the screenshot's dark greys and almost nothing brighter
            if bad or (share(png, lambda r, g, b: r + g + b >= 192) < 0.01 and share(png, lambda r, g, b: r + g + b >= 96) > 0.2):
                break
        if from_screen:
            return screen_qr(lambda: step("", "qr", 0)[0])
        (OUT / "signed.py").write_text(SIGNED)
        out = subprocess.run(DRIVE + ["exec", SOCK, str(OUT / "signed.py"), "8"], cwd=R, capture_output=True, text=True).stdout
    finally:
        serve.terminate()
        remove(port, "qr_inject.txt")
    m = re.findall(r"^B64 (\S+)", out, re.M)
    return base64.b64decode("".join(m)) if m else None


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("port"); a.add_argument("cases"); a.add_argument("names", nargs="*")
    a.add_argument("--reset"); a.add_argument("--upstream", default="ada81cde")
    args = a.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    cases = json.load(open(args.cases))
    for name in args.names or cases:
        raw = base64.b64decode(cases[name])
        print(f"{name}: {len(raw)} B")
        signed = run(args.port, name, raw, args.reset)
        if signed is None:
            print("  no signed PSBT")
            continue
        print(f"  signed {len(signed)} B, same as this machine's {signed == fork_signed(raw)}, as upstream's {signed == upstream_signed(raw, args.upstream)}")
