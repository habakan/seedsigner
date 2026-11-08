"""SeedSigner's Camera on the Pico: _camera captures and reads a QR code in C, so a "frame" from
read_video_stream() is the code's bytes, or NO_CODE, which DecodeQR takes as they are (pico/lib/pico_boot.py)."""
import _camera
from PIL import Image


# A frame without a code: not None, as ScanScreen reads the buttons only after a frame
NO_CODE = object()
# Development only (serial keys on): qr_inject.txt's lines stand in for what the camera reads, a "---" line
# ending each scan, so a flow can be measured without a screen to point it at
_inject = None
_inject_mid = False


class CameraConnectionError(Exception):
    pass


class Camera:
    _instance = None
    _video_stream = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start_video_stream_mode(self, resolution=None, framerate=None, format=None):
        try:
            _camera.open()  # borrows WAMR's pool, ending parser.wasm's instance until the next parse
        except OSError:
            raise CameraConnectionError()
        self._video_stream, self._animated = True, False
        global _inject
        from RPi import GPIO
        if GPIO.serial_keys and _inject is None:
            try:
                _inject = open("qr_inject.txt")
            except OSError:
                _inject = False
        self._injecting, self._injected = bool(_inject), 0

    def read_video_stream(self, as_image=False):
        global _inject_mid
        if not self._video_stream:
            raise Exception("Must call start_video_stream first.")
        if as_image:
            # The last frame read, which _gfx draws from the camera's memory: no pixels are copied
            frame = Image.Image("RGB", (240, 240), None)
            frame.add(("cam", None, 240, 240))
            return frame
        try:
            data = _camera.read(2 if self._animated else 0)  # 2: the reader's budget for animated parts
        except OSError:
            raise CameraConnectionError()
        if self._injecting:
            line = _inject.readline().strip()
            if not self._injected and _inject_mid:  # the last scan finished early: skip what it left
                while line and line != "---":
                    line = _inject.readline().strip()
            if line == "---" and not self._injected:
                line = _inject.readline().strip()
            self._injected += 1
            _inject_mid = bool(line) and line != "---"
            if not line or line == "---":
                self._injecting = False
                return NO_CODE
            data = line.encode()
        if not isinstance(data, bytes):
            return NO_CODE
        self._animated = data[:3].upper() == b"UR:"
        return data

    def stop_video_stream_mode(self):
        if self._video_stream:
            _camera.close()
            self._video_stream = None
