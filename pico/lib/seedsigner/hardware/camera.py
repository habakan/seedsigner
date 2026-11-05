"""SeedSigner's Camera on the Pico: _camera captures and reads a QR code in C, so a "frame" from
read_video_stream() is the code's bytes, or None, which DecodeQR takes as they are (pico/lib/pico_boot.py)."""
import _camera
from PIL import Image


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

    def read_video_stream(self, as_image=False):
        if not self._video_stream:
            raise Exception("Must call start_video_stream first.")
        if as_image:
            # No preview yet: a dark frame for ScanScreen to draw the progress on, between reads
            return Image.new("RGBA", (240, 240), "black")
        try:
            data = _camera.read(2 if self._animated else 0)  # 2: the reader's budget for animated parts
        except OSError:
            raise CameraConnectionError()
        if not isinstance(data, bytes):
            return None
        self._animated = data[:3].upper() == b"UR:"
        return data

    def stop_video_stream_mode(self):
        if self._video_stream:
            _camera.close()
            self._video_stream = None
