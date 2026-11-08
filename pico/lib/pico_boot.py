# What the Pico changes in SeedSigner as it starts, rather than in SeedSigner's source; main.py imports it
# before the Controller (pico/Makefile's device-install)
import seedsigner.controller as controller
from seedsigner.models.decode_qr import DecodeQR


def _preload(self):
    # The seed storage alone: the heap cannot hold every view's module at once, and each loads when first used
    from seedsigner.models.seed_storage import SeedStorage
    controller.Controller.get_instance()._storage = SeedStorage()


controller.BackgroundImportThread.run = _preload

_extract_qr_data = DecodeQR.extract_qr_data


def _bytes_or_frame(image, is_binary=False):
    # The Pico's camera reads the QR code itself (pico/lib/seedsigner/hardware/camera.py) and hands over its bytes
    from seedsigner.hardware.camera import NO_CODE
    if image is NO_CODE:
        return None
    if isinstance(image, (bytes, bytearray)):
        return bytes(image)
    return _extract_qr_data(image, is_binary)


DecodeQR.extract_qr_data = staticmethod(_bytes_or_frame)

from seedsigner.gui.screens.scan_screens import ScanScreen

_scan_post_init = ScanScreen.__post_init__


def _scan_without_preview_thread(self):
    # Drawn between camera reads (ScanScreen._run) instead: a read holds the GIL for seconds, and core1's
    # thread waiting on it left the screen black
    _scan_post_init(self)
    self.threads.remove(self.preview)


ScanScreen.__post_init__ = _scan_without_preview_thread

import pico_l10n
from seedsigner.models.settings_definition import SettingsConstants, SettingsDefinition


def _frozen_languages(cls=None):
    # The catalogs frozen as pico_l10n (pico/Makefile's LOCALES), where upstream walks resources/ on the filesystem
    return [(c, SettingsConstants.ALL_LOCALES[c]) for c in pico_l10n.LOCALES]


SettingsConstants.get_detected_languages = classmethod(_frozen_languages)
SettingsDefinition.get_settings_entry(SettingsConstants.SETTING__LOCALE).selection_options = _frozen_languages()

# A signed PSBT's UR, and a scanned one, without the 3-4 KB copies that a fragmented heap has no hole for
from seedsigner.helpers.ur2.fountain_encoder import FountainEncoder
from seedsigner.helpers.ur2.ur import UR
from seedsigner.helpers.ur2.ur_encoder import UREncoder
from seedsigner.models.encode_qr import BaseFountainQrEncoder, UrPsbtQrEncoder
from seedsigner.models.qr_type import QRType
from seedsigner.helpers.bitwasm import BitwasmReview

_UR_BUF = bytearray(4096)  # taken while the heap is whole: parser.wasm's trimmed output for 16 inputs is 2.5 KB


def _partition(message, fragment_len):
    # Each fragment copied out on its own, where upstream slices off the remainder, a fresh copy, per fragment
    mv, fragments = memoryview(message), []
    for at in range(0, len(mv), fragment_len):
        piece = mv[at:at + fragment_len]
        f = bytearray(fragment_len)
        f[:len(piece)] = piece
        fragments.append(f)
    return fragments


FountainEncoder.partition_message = staticmethod(_partition)


def _bstr_head(n):
    return bytes([0x40 | n]) if n < 24 else bytes([0x58, n]) if n < 256 else bytes([0x59, n >> 8, n & 255])


_signed = None


def _signed_into_ur_buf(out):
    # The signed PSBT written once, already as the UR's CBOR, where a bytes() copy needed a hole its size
    global _signed
    head = _bstr_head(len(out))
    n = len(head) + len(out)
    if n > len(_UR_BUF) or len(out) > 65535:
        return bytes(out)
    _UR_BUF[:len(head)] = head
    _UR_BUF[len(head):n] = out
    _signed = memoryview(_UR_BUF)[len(head):n]
    return _signed


BitwasmReview.signed_out = staticmethod(_signed_into_ur_buf)


def _ur_psbt_post_init(self):
    raw = self.psbt
    n = len(_bstr_head(len(raw))) + len(raw)
    # Single-part URs add the checksum by concatenation, which a memoryview does not do
    if raw is not _signed or n <= self.qr_max_fragment_size:
        if isinstance(raw, memoryview):
            self.psbt = bytes(raw)
        return _ur_psbt_init(self)
    BaseFountainQrEncoder.__post_init__(self)
    self.ur2_encode = UREncoder(ur=UR("crypto-psbt", memoryview(_UR_BUF)[:n]), max_fragment_len=self.qr_max_fragment_size)


_ur_psbt_init = UrPsbtQrEncoder.__post_init__
UrPsbtQrEncoder.__post_init__ = _ur_psbt_post_init

import gc
from binascii import crc32
from bitwasm_signer.signer import MAX_INPUTS, PLAN_N_INPUTS, PREVTX_MAX
from seedsigner.helpers import bitwasm


def _prevtx_buffer():
    # The firmware's prevtx_buf (modbitwasm.c); a wasm signer, on a PC, exposes it through its memory
    try:
        import _bitwasm
        return _bitwasm.prevtx_buffer()
    except ImportError:
        S = bitwasm._load_signer()
        return memoryview(S._m)[S._e.signer_prevtx():S._e.signer_prevtx() + PREVTX_MAX]
from seedsigner.helpers.bitwasm import BitwasmError
from seedsigner.helpers.ur2.fountain_decoder import FountainDecoder, InvalidChecksum
from seedsigner.helpers.ur2.ur_decoder import URDecoder

class _Pieces:
    # A scanned message as the UR fragments it came in: a real PSBT's prevtxs make it tens of KB, which the heap
    # has no hole for, and parser.wasm takes it piece by piece (helpers/bitwasm.py's chunks())
    def __init__(self, pieces, start, n, static_off=None):
        # static_off: its offset in the signer's prevtx buffer, when it is held there
        self.pieces, self.start, self.n, self.static_off = pieces, start, n, static_off

    def __len__(self):
        return self.n

    def chunks(self):
        skip, left = self.start, self.n
        for p in self.pieces:
            if skip >= len(p):
                skip -= len(p)
                continue
            mv = memoryview(p)[skip:skip + left]
            skip, left = 0, left - len(mv)
            yield mv
            if not left:
                return

    def __getitem__(self, s):
        # Slices from the start only, for a header or the PSBT magic
        out = bytearray()
        for c in self.chunks():
            out.extend(c[:s.stop - len(out)])
            if len(out) >= s.stop:
                break
        return bytes(out)

    def view(self, start, n):
        return _Pieces(self.pieces, self.start + start, n, None if self.static_off is None else self.static_off + start)

    def compact(self, size=2048):
        # The fragments into 2 KB pieces, in place (views share the list): 249 scattered 100-byte blocks cut
        # the free heap into holes too small for a screen. Stops at the first piece the heap has no room for
        if self.static_off is not None:
            return
        old, new, k = self.pieces, [], 0
        while k < len(old):
            n = min(size, sum(len(p) for p in old[k:k + size // 16 + 1]))
            try:
                piece = bytearray(n)
            except MemoryError:
                break
            filled = 0
            while filled < n:
                c = memoryview(old[k])[:n - filled]
                piece[filled:filled + len(c)] = c
                filled += len(c)
                if len(c) == len(old[k]):
                    old[k] = None
                    k += 1
                else:
                    old[k] = memoryview(old[k])[len(c):]
            new.append(piece)
        old[:] = new + old[k:]

    def tobytes(self):
        out = bytearray()
        for c in self.chunks():
            out.extend(c)
        return bytes(out)


class _Bits:
    # The received pure parts as one byte each, where a set rehashes into a bigger table as it fills
    def __init__(self, n):
        self.b, self.n = bytearray(n), 0

    def __contains__(self, i):
        return self.b[i] == 1

    def __len__(self):
        return self.n

    def add(self, i):
        self.n += 1 - self.b[i]
        self.b[i] = 1

    def discard(self, i):
        self.n -= self.b[i]
        self.b[i] = 0


class _Slots:
    # The dict FountainDecoder keeps parts in, as two lists sized once: a dict rehashes as it fills
    def __init__(self, n):
        self.keys, self.vals, self.n = [None] * n, [None] * n, 0

    def __len__(self):
        return self.n

    def _find(self, k):
        for j in range(self.n):
            if self.keys[j] == k:
                return j
        return -1

    def __setitem__(self, k, v):
        j = self._find(k)
        if j < 0:
            j, self.n = self.n, self.n + 1
        self.keys[j], self.vals[j] = k, v

    def __delitem__(self, k):
        self.pop(self._find(k))

    def pop(self, j):
        self.n -= 1
        self.keys[j], self.vals[j] = self.keys[self.n], self.vals[self.n]
        self.keys[self.n] = self.vals[self.n] = None

    def values(self):
        for j in range(self.n):
            yield self.vals[j]

    def items(self):
        for j in range(self.n):
            yield self.keys[j], self.vals[j]


def _validate_part(self, p):
    # As upstream, with every container sized at the first part, while the heap still has holes for them
    if self.expected_part_indexes is None:
        n = p.seq_len
        self.expected_part_indexes = set(range(n))
        self.expected_message_len, self.expected_checksum = p.message_len, p.checksum
        self.expected_fragment_len = len(p.data)
        self.by_index = [None] * n  # each pure part's data, in order
        self.received_part_indexes, self.simple_parts, self.mixed_parts = _Bits(n), _Slots(n), _Slots(n)
        _degree_sampler(n)
        self.static = None
        if getattr(self, "to_static", False) and n * self.expected_fragment_len <= PREVTX_MAX:
            # A PSBT's pure parts go to the signer's prevtx buffer as they come: 250 of them for 25 KB, kept in
            # the heap until the last, were what cut it up. One read before is let go, being written over
            self.static = _prevtx_buffer()
            c = controller.Controller.get_instance()
            if getattr(c.psbt_bytes, "static_off", None) is not None:
                c.psbt = c.psbt_bytes = c.psbt_parser = None
        return True
    return (self.expected_part_count() == p.seq_len and self.expected_message_len == p.message_len
            and self.expected_checksum == p.checksum and self.expected_fragment_len == len(p.data))


def _reduce_mixed_by(self, p):
    # In place, where upstream builds a new dict of them for every pure part
    m, j = self.mixed_parts, 0
    while j < m.n:
        r = self.reduce_part_by_part(m.vals[j], p)
        if r.is_simple():
            m.pop(j)
            self.enqueue(r)
        elif m._find(r.indexes) not in (-1, j):
            m.pop(j)
        else:
            m.keys[j], m.vals[j] = r.indexes, r
            j += 1


def _process_simple_part(self, p):
    i = p.index()
    if i in self.received_part_indexes:
        return
    if self.static is not None:
        fl = self.expected_fragment_len
        view = memoryview(self.static)[i * fl:(i + 1) * fl]
        view[:] = p.data
        p.data = view
    self.simple_parts[p.indexes] = p
    self.received_part_indexes.add(i)
    self.by_index[i] = p.data
    if len(self.received_part_indexes) != len(self.by_index):
        return self.reduce_mixed_by(p)
    crc, fl, total = 0, self.expected_fragment_len, self.expected_message_len
    for k, data in enumerate(self.by_index):
        crc = crc32(memoryview(data)[:min(fl, total - k * fl)], crc)
    if crc & 0xFFFFFFFF != self.expected_checksum:
        self.result = InvalidChecksum()
    elif self.static is not None:
        self.result = _Pieces([memoryview(self.static)[:total]], 0, total, 0)
    elif getattr(self, "to_static", False) and total <= PREVTX_MAX:
        # A PSBT goes out of the heap, into the signer's prevtx buffer: it stays until signing, while the
        # screens and the camera cut the heap around it. Its prevtxs are read there in place (put_prevtxs)
        buf = _prevtx_buffer()
        for k, data in enumerate(self.by_index):
            n = min(fl, total - k * fl)
            buf[k * fl:k * fl + n] = memoryview(data)[:n]
        self.result = _Pieces([memoryview(buf)[:total]], 0, total, 0)
    else:
        # The fragments themselves are the pieces: by now the heap has no hole even for a copy of one
        self.result = _Pieces(self.by_index, 0, total)
    # Only the pieces stay: the leftover mixed parts and the degree table are as large again
    self.simple_parts, self.mixed_parts, self.queued_parts, self.by_index = {}, {}, [], None
    _sampler[:] = [0, None]


from seedsigner.helpers.ur2 import fountain_decoder, fountain_encoder, fountain_utils
from seedsigner.helpers.ur2.random_sampler import RandomSampler
from seedsigner.helpers.ur2.utils import int_to_bytes
from seedsigner.helpers.ur2.xoshiro256 import Xoshiro256

_sampler = [0, None]


def _degree_sampler(seq_len):
    if _sampler[0] != seq_len:
        sampler = RandomSampler([1.0 / i for i in range(1, seq_len + 1)])
        _sampler[:] = [seq_len, sampler]
    return _sampler[1]


def _choose_fragments(seq_num, seq_len, checksum):
    # As upstream, with the degree table built once per message: rebuilt for every mixed part, its 1 KB lists
    # failed in a fragmented heap and the part was dropped
    if seq_num <= seq_len:
        return {seq_num - 1}
    rng = Xoshiro256.from_bytes(int_to_bytes(seq_num) + int_to_bytes(checksum))
    degree = _degree_sampler(seq_len).next(lambda: rng.next_double()) + 1
    # upstream pops each pick from list(range(seq_len)): the k-th value not yet taken is the same pick
    taken = []
    for left in range(seq_len, seq_len - degree, -1):
        v = rng.next_int(0, left - 1)
        for t in taken:  # ascending
            if t <= v:
                v += 1
        taken.append(v)
        taken.sort()
    return set(taken)


fountain_utils.choose_fragments = fountain_decoder.choose_fragments = fountain_encoder.choose_fragments = _choose_fragments
FountainDecoder.validate_part = _validate_part
FountainDecoder.reduce_mixed_by = _reduce_mixed_by
FountainDecoder.process_simple_part = _process_simple_part
_receive_part = URDecoder.receive_part


def _receive_part_whole(self, part):
    # Only a PSBT stays in pieces, and goes to the prevtx buffer; descriptors and the like are small and read
    # with BytesIO, and one scanned while a PSBT is reviewed must not overwrite it there
    try:
        self.fountain_decoder.to_static = URDecoder.parse(part)[0] in ("crypto-psbt", "psbt")
    except Exception:
        pass
    r = _receive_part(self, part)
    res = self.result
    if res is not None and not isinstance(res, Exception) and isinstance(res.cbor, _Pieces) \
            and res.type not in ("crypto-psbt", "psbt"):
        res.cbor = res.cbor.tobytes()
    return r


URDecoder.receive_part = _receive_part_whole
_put_prevtxs = BitwasmReview.put_prevtxs


def _put_prevtxs_in_place(self, S, P, at):
    # A PSBT held in the prevtx buffer has its prevtxs there already: point the signer at them, copying nothing
    base = getattr(self.psbt_bytes, "static_off", None)
    if base is None:
        return _put_prevtxs(self, S, P, at)
    for i in range(MAX_INPUTS):
        n = P.parser_prevtx_len(i) if i < self.plan[PLAN_N_INPUTS] else 0
        if not S._e.signer_set_prevtx(i, base + P.parser_prevtx_off(i) if n else 0, n):
            raise BitwasmError(f"prevtx {i} is outside the prevtx buffer")


BitwasmReview.put_prevtxs = _put_prevtxs_in_place
_get_psbt, _get_data_psbt = DecodeQR.get_psbt, DecodeQR.get_data_psbt


def _unwrapped_psbt(self):
    # The PSBT inside its CBOR byte string, as a view of the same pieces
    if getattr(self, "_psbt", None) is None:
        buf = self.decoder.result_message().cbor
        if not isinstance(buf, _Pieces):
            return _get_data_psbt(self)
        head = buf[0:3]
        ai = head[0] & 31
        if head[0] >> 5 != 2 or ai > 25:
            return None
        h = 1 if ai < 24 else ai - 22
        n = ai if ai < 24 else int.from_bytes(head[1:h], "big")
        if h + n > len(buf):
            return None
        self._psbt = buf.view(h, n)
    return self._psbt


def _get_psbt_ur(self):
    if not (self.complete and self.qr_type == QRType.PSBT__UR2):
        return _get_psbt(self)
    data = _unwrapped_psbt(self)
    if not isinstance(data, _Pieces):
        return None if data is None else _get_psbt(self)
    if not DecodeQR.is_psbt_bytes(data):
        return None
    gc.collect()  # the scan screen's and the decoder's leftovers, so the pieces find room
    data.compact()
    return data


def _get_data_psbt_ur(self):
    if self.complete and self.qr_type == QRType.PSBT__UR2:
        return _unwrapped_psbt(self)
    return _get_data_psbt(self)


DecodeQR.get_psbt, DecodeQR.get_data_psbt = _get_psbt_ur, _get_data_psbt_ur

import time
from PIL.Image import box
from seedsigner.gui.components import GUIConstants, linear_interp
from seedsigner.gui.screens.psbt_screens import PSBTOverviewScreen


def _pulses(self):
    # As upstream's run, but a pulse's trailing grey takes its segments off the canvas, showing the chart's own
    # grey lines beneath (#666, 3 px), rather than piling ~80 grey copies into a heap the review left in holes
    pulse_color, line_width = GUIConstants.ACCENT_COLOR, 3
    canvas, color = self.renderer.canvas, self.renderer.draw._c(GUIConstants.ACCENT_COLOR)
    start_pt, end_pt = self.inputs[0][-1], self.outputs[0][0]
    if start_pt == end_pt:
        center_bar_pts = [end_pt, self.outputs[0][1]]
    else:
        mid = [linear_interp(start_pt, end_pt, t) for t in (0.25, 0.5, 0.75)]
        center_bar_pts = [start_pt] + [(int(p[0]), int(p[1])) for p in mid] + [end_pt]
    # Each step's segments and their boxes, made once while the screen's heap is still whole
    steps = [[[p[i], p[i + 1]] for p in curves] for curves, n in
             ((self.inputs, len(self.inputs[0])), ([center_bar_pts], len(center_bar_pts)), (self.outputs, len(self.outputs[0])))
             for i in range(n - 1)]
    steps = [[(pts, box(("line", pts, 0, line_width))) for pts in s] for s in steps]

    def draw(k, pulse):
        for pts, b in steps[k]:
            if pulse:
                canvas.add(("line", pts, color, line_width), b)
                continue
            for i in range(len(canvas.ops) - 1, -1, -1):
                if canvas.ops[i][0] == "line" and canvas.ops[i][1] is pts:
                    del canvas.ops[i], canvas.boxes[i]
            d = canvas.dirty
            canvas.dirty = b if d is None else (min(d[0], b[0]), min(d[1], b[1]), max(d[2], b[2]), max(d[3], b[3]))

    pulses, prev_pulse = [], False
    while self.keep_running:
        with self.renderer.lock:
            if not pulses or (prev_pulse and pulses[-1][0] == 10):
                pulses.append([0, not prev_pulse])
                prev_pulse = pulses[-1][1]
            for pulse_num, pulse in enumerate(pulses):
                if pulse[0] >= len(steps):
                    del pulses[pulse_num]
                    continue
                draw(pulse[0], pulse[1])
                pulse[0] += 1
            self.renderer.show_image()
        time.sleep(0.02)


PSBTOverviewScreen.TxExplorerAnimationThread.run = _pulses

from seedsigner.hardware.camera import Camera
from seedsigner.views.tools_views import ToolsImageEntropyMnemonicLengthView
import seedsigner.gui.screens.tools_screens as _tools_screens


class _RecentHashes(list):
    # The entropy preview's repeated-frame check, against the last 64 frames: upstream's set takes every frame shown
    # until the button press, and outgrew the heap within a minute of the pool filling
    def add(self, h):
        if len(self) == 64:
            self.pop(0)
        self.append(h)


_tools_screens.set = _RecentHashes  # the module's only set()

_mnemonic_length_run = ToolsImageEntropyMnemonicLengthView.run


def _wiping_final_image(self):
    # The final image is shown from the camera's memory, which stays borrowed until the words are made of it
    try:
        return _mnemonic_length_run(self)
    finally:
        if not self.controller.image_entropy_final_image:
            Camera.get_instance().release()


ToolsImageEntropyMnemonicLengthView.run = _wiping_final_image
