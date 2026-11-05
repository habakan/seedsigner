"""
helpers/qr.py of the Pico against SeedSigner's own, on CPython: each QR code drawn through the PIL shim and
gfx_sim is read back with zbarimg. qrcode scores masks its own way, so where it picked another the version
is compared; with the same matrix the pixels are, to within PIL's resampled edges.

    python3 pico/tests/check_qr.py OUT_DIR
"""
import importlib.util, pathlib, subprocess, sys, types

root = pathlib.Path(__file__).resolve().parents[2]
out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(root / "src"))
from seedsigner.helpers.qr import QR as RealQR  # real PIL and qrcode, before the shim takes "PIL"

CASES = [
    ("ur", "UR:CRYPTO-PSBT/12-3/LPCSESKPADCFAXHLCYYNLUFZKBHDCWYLFZRYRPTYAXONYLAEMYDYGHWSJKCSGOEMTPRFLDPAOLRLYLY"),
    ("seedqr", "175603411269118918791714206209390720081903821603155206310918640202130512650510"),
    ("compact", bytes(range(16))),
    ("address", "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"),
]
VARIANTS = (("io", 1), ("img", 1), ("img", 2), ("img", 3))
SEEDQR = ("seedqr", "compact")  # SeedSigner draws dots (style 2) only for SeedQR's 21x21 to 29x29


def args(fn, style):
    size = 200 if style == 2 else 240
    if fn == "io":
        return size, dict(border=2), "bdbdbd"
    return size, dict(border=1 if style == 2 else 3, style=style), "#fff"  # SeedSigner's #444 is too dark for zbar


# SeedSigner's own pictures, as dark/light per pixel, and qrcode's matrices
import qrcode
refs, matrices = {}, {}
for name, data in CASES:
    q = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, border=0)
    q.add_data(data)
    q.make(fit=True)
    matrices[name] = q.get_matrix()
    for fn, style in VARIANTS:
        if style == 2 and name not in SEEDQR:
            continue
        size, kw, bg = args(fn, style)
        ref = RealQR().qrimage(data, size, size, background_color="#" + bg.lstrip("#"), **kw).convert("L")
        refs[name, fn, style] = [v < 64 for v in ref.getdata()]

for k in [k for k in sys.modules if k == "PIL" or k.startswith("PIL.")]:
    del sys.modules[k]
shim = types.ModuleType("PIL")
shim.__path__ = [str(root / "pico/lib/PIL")]
sys.modules["PIL"] = shim
sys.path.insert(0, str(root / "pico/tests"))
import gfx_sim
sys.modules["_gfx"] = gfx_sim
spec = importlib.util.spec_from_file_location("pico_qr", root / "pico/lib/seedsigner/helpers/qr.py")
pico_qr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pico_qr)
from PIL import ImageDraw


def to_ppm(canvas, path):
    path.write_bytes(b"P6 240 240 255\n" + bytes(c for v in canvas for c in gfx_sim.RGB[v]))


def zbar(path):
    r = subprocess.run(["zbarimg", "-q", "--raw", "-Sbinary", str(path)], capture_output=True)
    return r.stdout


bad = 0
for name, data in CASES:
    for fn, style in VARIANTS:
        if style == 2 and name not in SEEDQR:
            continue
        size, kw, bg = args(fn, style)
        if fn == "io":
            im = pico_qr.QR().qrimage_io(data, size, size, background_color=bg, **kw)
        else:
            im = pico_qr.QR().qrimage(data, size, size, background_color=bg, **kw)
        gfx_sim.canvas_bytes[:] = bytes([gfx_sim.colour(255, 255, 255)]) * (240 * 240)
        ImageDraw.replay(im.ops, 0, 0, (0, 0, 240, 240))
        path = out / ("%s-%s%d.ppm" % (name, fn, style))
        to_ppm(gfx_sim.canvas_bytes, path)
        got = zbar(path)
        want = data.encode() if isinstance(data, str) else data
        # Few differing pixels means qrcode picked the same version and mask, and the modules land alike
        ref = refs[name, fn, style]
        diff = sum(1 for y in range(size) for x in range(size)
                   if ref[y * size + x] != (sum(gfx_sim.RGB[gfx_sim.canvas_bytes[y * 240 + x]]) < 192))
        code, m = gfx_sim.qr_encode(data), matrices[name]
        n = code[0]
        same = len(m) == n and all(m[i // n][i % n] == bool(code[1 + (i >> 3)] >> (i & 7) & 1) for i in range(n * n))
        ok = got == want and len(m) == n and (not same or diff * 100 < size * size * (8 if style == 1 else 12))
        bad += not ok
        print("%-8s %-4s style %d  read %-3s  %dx%d %s" % (name, fn, style, "ok" if got == want else "NO", n, n,
              "%.1f%% pixels differ from SeedSigner's" % (100 * diff / size / size) if same else
              "(qrcode's mask differs)" if len(m) == n else "but qrcode's is %dx%d" % (len(m), len(m))))
sys.exit(1 if bad else 0)
