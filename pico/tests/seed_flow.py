"""
A new seed from the camera on the device, through SeedSigner's own screens with the dev main.py: Tools, New seed
(camera), 50 preview frames, the final image, 12 words, then its SeedQR and its native segwit xpub as a static QR,
both read off screenshots. The SeedQR's words must be a valid BIP39 mnemonic whose xpub, derived here, is the one
the device shows; each run's seed must differ from the others'. The camera sees whatever is in front of it.

    .venv/bin/python pico/tests/seed_flow.py PORT [--runs N] [--network M|T] [--linger SECS] [--reset CMD]

Needs zbar (DYLD_LIBRARY_PATH=/opt/homebrew/lib on macOS). Screenshots, the words among them, go to build/pico/seed_flow.
"""
import argparse, subprocess, sys, time
from embit import bip32, bip39
from embit.networks import NETWORKS
from embit.wordlists.bip39 import WORDLIST
import psbt_flow as F

OUT = F.R / "build/pico/seed_flow"


def read_qr(png):
    from PIL import Image
    from pyzbar.pyzbar import decode
    codes = decode(Image.open(png).convert("L").resize((720, 720), Image.NEAREST))
    return codes[0].data.decode() if codes else None


def run(port, n, network, reset, linger):
    log = OUT / f"run{n}.log"
    log.write_bytes(b"")
    if reset:
        subprocess.run(reset, shell=True, capture_output=True, timeout=60)
        time.sleep(25)
    # Read once at boot: upstream's Settings then removes it, persistent settings being off
    conf = '{"network": "%s"}' % network
    if not any(F.put(port, "settings.json", conf) == str(len(conf)) for _ in range(3)):  # any: stops at the first
        sys.exit("settings.json did not reach the device")
    serve = subprocess.Popen(F.DRIVE + ["serve", port, F.SOCK, str(log)], cwd=F.R,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        def shot(png):
            subprocess.run(F.DRIVE + ["send", F.SOCK, "", str(png)], cwd=F.R, capture_output=True)
            return png.read_bytes()

        def step(keys, label, wait=1):
            png = OUT / f"run{n}_{label}.png"
            before = shot(png)
            for k in keys:
                # One at a time, again until the screen changes: a screen just drawn may not take a key yet
                for _ in range(4):
                    subprocess.run(F.DRIVE + ["send", F.SOCK, k], cwd=F.R, capture_output=True)
                    time.sleep(wait)
                    if shot(png) != before or (time.sleep(2) or shot(png) != before):  # a slow screen, not a lost key
                        break
                before = png.read_bytes()
            if not keys:
                time.sleep(wait)
                shot(png)
            if "Traceback" in log.read_bytes().decode(errors="replace"):
                sys.exit(f"an exception at {label}; see {log}")
            return png

        boot = time.time()
        # Home's orange Scan button, once main.py's boot is through: a soft reboot takes 30 s or more
        while F.share(step("", "home", 5), lambda r, g, b: r > 200 and 100 < g < 180 and b < 60) < 0.12:  # the splash has 0.1
            if time.time() - boot > 120:
                sys.exit("no home screen in 2 minutes")
        time.sleep(8)  # the 5 s "remove the SD card" toast: its thread beside the camera's preview ran out of heap
        step("dp", "tools")
        start = time.time()
        green = lambda png: F.share(png, lambda r, g, b: g > 180 and r < 80 and b < 80)
        png, seen = step("p", "preview", 3), False
        # the frame counter's green bar, which gives way to "click a button" once the pool holds all 50
        while not (seen and green(png) == 0):
            seen |= green(png) > 0
            if time.time() - start > 180:
                sys.exit("the preview pool did not fill in 3 minutes")
            png = step("", "preview", 2)
        print(f"  50 preview frames in {time.time() - start:.0f} s")
        time.sleep(linger)  # the preview goes on taking frames until the press, which once ran the heap out
        step("", "preview_held")
        step("p", "final", 3)
        step("r", "length")
        step("p", "warning", 10)  # Calculating...
        for page in (1, 2, 3):
            step("p", f"words{page}")
        step("p", "verify")  # the last page's Next
        step("d", "verify_skip")
        step("p", "finalize", 3)
        step("p", "options", 2)
        step("dddp", "backup")
        step("dp", "seedqr_format")
        step("p", "seedqr_warning")
        digits = read_qr(step("p", "seedqr", 3))
        step("p", "seedqr_zoom")  # the transcription's zoomed squares
        step("p", "seedqr_confirm")  # click to exit
        step("dp", "options2", 2)
        step("dp", "xpub_sigtype")
        step("p", "xpub_script")
        step("p", "xpub_format")
        step("dp", "xpub_warning")  # Static
        step("p", "xpub_details", 3)
        xpub = read_qr(step("p", "xpub_qr", 4))
    finally:
        serve.terminate()
    return digits, xpub


def expected_xpub(words, network):
    net = NETWORKS["main" if network == "M" else "test"]
    root = bip32.HDKey.from_seed(bip39.mnemonic_to_seed(words))
    path = "m/84h/%dh/0h" % (0 if network == "M" else 1)
    return "[%s%s]%s" % (root.my_fingerprint.hex(), path[1:], root.derive(path).to_public().to_base58(net["zpub"]))


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("port"); a.add_argument("--runs", type=int, default=2)
    a.add_argument("--network", default="T", choices="MT"); a.add_argument("--reset")
    a.add_argument("--linger", type=int, default=60, help="seconds to leave the full preview running")
    args = a.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    seeds, failed = set(), 0
    for n in range(1, args.runs + 1):
        print(f"run {n}")
        digits, xpub = run(args.port, n, args.network, args.reset, args.linger)
        if not digits or len(digits) != 48:
            print("  no SeedQR read"); failed += 1; continue
        words = " ".join(WORDLIST[int(digits[i:i + 4])] for i in range(0, 48, 4))
        valid = bip39.mnemonic_is_valid(words)
        same = (xpub or "").replace("'", "h") == expected_xpub(words, args.network)  # the device writes 84'
        print(f"  valid BIP39 {valid}, xpub as derived here {same}: {xpub}")
        failed += not (valid and same) or words in seeds
        seeds.add(words)
    print(f"{args.runs - failed} of {args.runs} runs made a distinct, valid seed whose xpub matches")
    sys.exit(1 if failed else 0)
