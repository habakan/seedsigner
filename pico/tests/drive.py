"""
Drives SeedSigner on the device over USB serial, with the dev main.py (make device-install-dev). One process
holds the port, reading it all the time (closing and reopening it wedges the rp2 port's USB serial, and
unread output stalls the device's prints), and takes commands on a Unix socket:

    python3 pico/tests/drive.py serve PORT SOCKET LOG      # reboots into main.py; device output goes to LOG
    python3 pico/tests/drive.py sim DIR SOCKET LOG          # the same with pico/tests/sim_main.py run in DIR
    python3 pico/tests/drive.py send SOCKET KEYS [OUT.png]  # presses KEYS (u d l r p 1 2 3), then a screenshot
    python3 pico/tests/drive.py exec SOCKET FILE.py [SECS]  # ^C, then FILE pasted at the REPL; prints its output

Keys are held 300 ms each by pico/lib/RPi/GPIO.py; a screenshot is the framebuffer, run-length encoded.
"""
import base64, os, pathlib, socket, sys, threading, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))


class Sim:
    """MicroPython's unix port, built by make -C pico sim, running sim_main.py: a port of its stdin and stdout."""
    def __init__(self, cwd):
        import subprocess
        r = pathlib.Path(__file__).resolve().parents[2]
        mpy = os.environ.get("SIM_MICROPYTHON", str(r / "build/micropython/ports/unix/build-sim/micropython"))
        self.p = subprocess.Popen([mpy, "-X", "heapsize=1024k",
                                   str(r / "pico/tests/sim_main.py")], cwd=cwd, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def read(self, n):
        return os.read(self.p.stdout.fileno(), n)

    def write(self, b):
        self.p.stdin.write(b)
        self.p.stdin.flush()


def serve(port, path, log, s=None):
    if s is None:
        import serial
        s = serial.Serial(port, 115200, timeout=0.1)
        s.write(b"\x03"); time.sleep(0.5); s.write(b"\x02"); time.sleep(0.5)
        s.write(b"\x04")  # soft reboot: runs main.py
    buf, lock = bytearray(), threading.Lock()
    out = open(log, "ab", buffering=0)

    def reader():
        while True:
            c = s.read(65536)
            if c:
                with lock:
                    buf.extend(c)
                out.write(c)

    threading.Thread(target=reader, daemon=True).start()
    if os.path.exists(path):
        os.remove(path)
    srv = socket.socket(socket.AF_UNIX)
    srv.bind(path)
    srv.listen(1)
    while True:
        conn, _ = srv.accept()
        keys = conn.recv(65536).decode()
        if keys.startswith("exec:"):
            secs, code = keys[5:].split(":", 1)
            with lock:
                del buf[:]
            s.write(b"\x03\x03")
            time.sleep(0.5)
            s.write(b"\x05" + code.encode().replace(b"\n", b"\r") + b"\x04")  # paste mode
            time.sleep(float(secs))
            with lock:
                conn.sendall(bytes(buf))
            conn.close()
            continue
        for k in keys:
            s.write(k.encode())
            time.sleep(0.35)
        time.sleep(0.8)
        with lock:
            del buf[:]
        s.write(b"s")
        end, data = time.time() + 60, b""  # a camera frame is ~130 KB of rows at 115200 baud
        while time.time() < end:
            with lock:
                if b"FB>>" in buf:
                    data = bytes(buf)
                    break
            time.sleep(0.05)
        if b"<<FB" in data:
            conn.sendall(data.split(b"<<FB", 1)[1].split(b"FB>>", 1)[0])
        conn.close()


def send(path, keys, png):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "third_party/micropython-pil/PIL"))
    import _gfx_sim as gfx_sim
    from PIL import Image
    c = socket.socket(socket.AF_UNIX)
    c.connect(path)
    c.sendall(keys.encode() or b" ")
    data = b""
    while True:
        d = c.recv(65536)
        if not d:
            break
        data += d
    if not data:
        sys.exit("no screenshot; is main.py running? see the log")
    rle, px = b"".join(base64.b64decode(line) for line in data.split() if line), []
    for i in range(0, len(rle), 2):
        px += [gfx_sim.RGB[rle[i + 1]]] * rle[i]
    img = Image.new("RGB", (240, 240))
    img.putdata(px[:240 * 240])
    img.save(png)
    print("saved", png)


def exec_(path, file, secs):
    c = socket.socket(socket.AF_UNIX)
    c.connect(path)
    c.sendall(("exec:%s:" % secs).encode() + open(file, "rb").read())
    data = b""
    while True:
        d = c.recv(65536)
        if not d:
            break
        data += d
    print(data.decode(errors="replace").replace("\r", ""))


if sys.argv[1] == "exec":
    exec_(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "10")
elif sys.argv[1] == "serve":
    serve(*sys.argv[2:5])
elif sys.argv[1] == "sim":
    import signal
    sim = Sim(sys.argv[2])
    signal.signal(signal.SIGTERM, lambda *a: (sim.p.kill(), sys.exit()))  # psbt_flow.py ends a run so
    serve(None, *sys.argv[3:5], s=sim)
else:
    send(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "/dev/null")
