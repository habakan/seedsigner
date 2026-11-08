"""
Review and signing through bitwasm-signer's parser.wasm and signer.wasm, on WAMR.

embit still reads the psbt for the screens, but nothing is signed unless signer.wasm's own
review of the same bytes agrees with it, and only signer.wasm signs. See
PSBTParser._check_with_bitwasm for what has to agree.

Seeds are derived inside signer.wasm. It holds one key at a time: the seed last passed to use().

The modules are bitwasm-signer 91d2c5d's build/parser.wasm and build/signer.wasm, pinned
by hash. libiwasm (WAMR 2.4.5, classic interpreter) comes from the OS image. On MicroPython the
signer is the same C linked into the firmware, which the Pico could not afford to interpret.
"""
import hashlib
import logging
import os
import sys

from bitwasm_signer import Instance, Signer, SignerError
from bitwasm_signer.signer import MAX_INPUTS, NONCE_SIZE, PLAN_N_INPUTS, PLAN_SIZE, SIG_SIZE

from seedsigner.models.settings import SettingsConstants

logger = logging.getLogger(__name__)

PARSER_SHA256 = "17574da292779c2944b210feb1fb5e4f66af5e2fd33f95a1351868405ca9c071"
# The Pico assembles UR in Python, so it runs the build without the UR decoder: 42 KB less of WAMR's pool
PARSER_NO_UR_SHA256 = "b675b59f88d2ce13af53c2c8320948afbf170adace162b063e736acc425f4627"
SIGNER_SHA256 = "c760e714be601dc12583110926f39f9ace21823cbb5d7d33f5282abc4ced3faa"

# Upstream's rules: OP_RETURN of complete pushes only, and SegWit v0 inputs signed without non_witness_utxo
SIGNER_OPTIONS = {"strict_op_return": True, "prevtx_optional": True}

OWNER_EXTERNAL, OWNER_CHANGE, OWNER_SELF = 0, 1, 2

# plan_t, from parser/c/include/plan.h (its _Static_asserts pin these): inputs and outputs, and in
# each the keypath {depth u8, fingerprint u32, path u32[8]} and the scriptPubKey {len u8, bytes[83]}
PLAN_INPUTS, PLAN_INPUT_SIZE, PLAN_OUTPUTS, PLAN_OUTPUT_SIZE, PLAN_WSCRIPTS, PLAN_WSCRIPT_SIZE = 24, 176, 2840, 136, 5016, 522
PLAN_IN_SPK, PLAN_IN_KEY, PLAN_OUT_SPK, PLAN_OUT_KEY = 48, 132, 8, 92
TEXT_KIND_OP_RETURN = 1

P_ERRORS = {1: "MAGIC", 2: "FORMAT", 3: "DUPLICATE", 4: "TX", 5: "UNSUPPORTED", 6: "LIMIT", 7: "UTXO", 8: "SIG",
            9: "UTXO_MISMATCH"}

_parser = None
_signer = None
_active = None
_registered = None  # (seed, network, descriptor) of the multisig the signer holds, and what loading it said



class BitwasmError(Exception):
    pass



def _read(name: str) -> bytes:
    if sys.implementation.name == "micropython":
        import bitwasm_modules  # frozen into the firmware by pico/Makefile; the device has no resources/
        return bitwasm_modules.PARSER
    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "bitwasm", name), "rb") as f:
        return f.read()



class _NativeSigner(Signer):
    """signer.wasm's exports as the firmware's own functions; there are no wasm bytes to hash."""
    def __init__(self):
        self._e = Instance(None)
        self._m = self._e.memory
        self._reviewed = False



def _load_parser():
    """One parser instance per process, read and hash-checked on first use."""
    global _parser
    # On the Pico the camera borrows WAMR's pool while it scans, which ends the instance
    if _parser is None or not getattr(_parser, "alive", lambda: True)():
        pico = sys.implementation.name == "micropython"
        wasm = _read("parser-no-ur.wasm" if pico else "parser.wasm")
        if hashlib.sha256(wasm).digest().hex() != (PARSER_NO_UR_SHA256 if pico else PARSER_SHA256):
            raise BitwasmError("parser.wasm is not the pinned build")
        _parser = Instance(wasm)
    return _parser



def _load_signer() -> Signer:
    global _signer
    if _signer is None:
        if sys.implementation.name == "micropython":
            _signer = _NativeSigner().init(**SIGNER_OPTIONS)
        else:
            _signer = Signer(_read("signer.wasm"), sha256=SIGNER_SHA256).init(**SIGNER_OPTIONS)
    return _signer



def use(seed, network: str = None) -> Signer:
    """
    signer.wasm with `seed`'s key loaded, deriving it only when another seed was loaded last.
    A network re-inits the module, which keeps the key but drops any review or multisig wallet.
    """
    global _active, _registered
    S = _load_signer()
    if _active is not seed:
        _active = _registered = None
        seed.load_into(S)
        _active = seed
    if network is not None:
        _registered = None
        # Strict OP_RETURN, as SeedSigner refuses one Bitcoin Core will not relay
        S.init(testnet=network != SettingsConstants.MAINNET, **SIGNER_OPTIONS)
    return S


def use_multisig(seed, network: str, descriptor: str) -> dict:
    """Registers `descriptor` with `seed`'s key, unless it is what the signer holds already, and returns what
    loading it said. Raises SignerError when the seed holds none of its keys or the descriptor is not one it reads."""
    global _registered
    if _registered and _registered[0] is seed and _registered[1:3] == (network, descriptor):
        return _registered[3]
    S = use(seed, network)
    _registered = (seed, network, descriptor, S.multisig_load(descriptor))
    return _registered[3]


def watch_multisig(network: str, descriptor: str) -> dict:
    """Registers `descriptor` for its addresses alone, needing no seed of ours, as use_multisig() does for signing."""
    global _registered
    if _registered and _registered[0] is None and _registered[1:3] == (network, descriptor):
        return _registered[3]
    S = _load_signer()
    _registered = None
    S.init(testnet=network != SettingsConstants.MAINNET, **SIGNER_OPTIONS)
    _registered = (None, network, descriptor, S.multisig_watch(descriptor))
    return _registered[3]



def as_psbt(data):
    """A bytearray, or the Pico's scanned PSBT in pieces (chunks()), as it is; anything else as bytes."""
    return data if isinstance(data, bytearray) or hasattr(data, "chunks") else bytes(data)


def _put_psbt(P, psbt):
    at = P.parser_input()
    for c in psbt.chunks() if hasattr(psbt, "chunks") else (psbt,):
        P.memory[at:at + len(c)] = c
        at += len(c)


def plan_fingerprints(psbt_bytes: bytes, fingerprint: int) -> bool:
    """Whether parser.wasm finds any input claiming `fingerprint`: a routing hint, as in SeedSigner."""
    P = _load_parser()
    if len(psbt_bytes) > P.parser_input_cap():
        return False
    _put_psbt(P, psbt_bytes)
    if P.parser_parse(len(psbt_bytes), fingerprint) != 0:
        return False
    plan = P.parser_plan()
    return any(P.memory[plan + PLAN_INPUTS + i * PLAN_INPUT_SIZE + PLAN_IN_KEY] for i in range(P.memory[plan + PLAN_N_INPUTS]))



def signer() -> Signer:
    """signer.wasm for what needs no key: new mnemonics and SeedQRs."""
    return _load_signer()



def forget(seed=None):
    """Unloads the key, or only `seed`'s when given."""
    global _active, _registered
    if seed is None or _active is seed:
        _active = _registered = None
        if _signer is not None:
            _signer.unload()



class Wordlist:
    """signer.wasm's English wordlist, read from its memory rather than copied into the heap."""
    def __init__(self):
        S = _load_signer()
        self._m, self._at = S._m, S._e.signer_wordlist()

    def __len__(self):
        return 2048

    def __getitem__(self, i):
        if isinstance(i, slice):
            return [self[j] for j in range(*i.indices(2048))]
        if i < 0:
            i += 2048
        if not 0 <= i < 2048:
            raise IndexError("wordlist index out of range")
        at = self._at + 8 * i
        return bytes(self._m[at:at + 8]).split(b"\0", 1)[0].decode()

    def __iter__(self):
        return (self[i] for i in range(2048))

    def index(self, word):
        lo = self._bisect(word)
        if lo < 2048 and self[lo] == word:
            return lo
        raise ValueError(f"{word!r} is not in the dictionary")

    def _bisect(self, word):
        lo, hi = 0, 2048
        while lo < hi:
            mid = (lo + hi) // 2
            if self[mid] < word:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def with_prefix(self, prefix):
        """The words starting with `prefix`, found by bisecting rather than by making all 2048 of them."""
        return [self[i] for i in range(self._bisect(prefix), self._bisect(prefix + "\x7f"))]

    def __contains__(self, word):
        try:
            self.index(word)
            return True
        except (ValueError, TypeError):
            return False



# Read once a review, right after it. The Pico fills the native signer's own plan, which the heap could not spare
# 13 KB for; elsewhere one buffer is taken at import
try:
    from _bitwasm import plan_buffer
    _plan = plan_buffer()
except ImportError:
    _plan = bytearray(PLAN_SIZE)


class BitwasmReview:
    """
    signer.wasm's review of one psbt for one seed: `display` is what it would sign.

    sign() parses and reviews the same bytes again and refuses unless the display is
    unchanged, so what was compared with the screens is what gets signed.
    """
    # What sign() returns the PSBT in; the Pico's pico_boot puts it where the UR encoder reads it
    signed_out = bytes

    def __init__(self, psbt_bytes: bytes, seed, network: str, multisig_descriptor: str | None = None):
        # Not copied: sign() reviews it again and refuses if it changed
        self.psbt_bytes = as_psbt(psbt_bytes)
        self.seed = seed
        self.network = network
        self.multisig_descriptor = multisig_descriptor
        self.wallet_registered = False
        self.unverified_change = False  # set by WasmPSBTParser for P2WSH change the psbt claims and no descriptor proved
        self.display = self._review()


    def _review(self) -> dict:
        P = _load_parser()
        S = use(self.seed, self.network)

        self.wallet_registered = False
        if self.multisig_descriptor:
            try:
                use_multisig(self.seed, self.network, self.multisig_descriptor)
                self.wallet_registered = True
            except SignerError as e:
                # Its change is then shown as external, as without a descriptor
                logger.info(f"signer.wasm did not register the descriptor: {e}")

        if len(self.psbt_bytes) > P.parser_input_cap():
            raise BitwasmError("PSBT too large")
        at = P.parser_input()
        _put_psbt(P, self.psbt_bytes)
        rc = P.parser_parse(len(self.psbt_bytes), int(S.fingerprint, 16))
        if rc != 0:
            raise BitwasmError(f"parser: {P_ERRORS.get(rc, rc)}")

        _plan[:] = memoryview(P.memory)[P.parser_plan():P.parser_plan() + PLAN_SIZE]  # no slice copy
        self.plan = plan = _plan
        self.put_prevtxs(S.set_plan(plan), P, at)
        try:
            self.review = S.review()
            return S.display()
        except SignerError as e:
            raise BitwasmError(str(e)) from e


    def put_prevtxs(self, S, P, at):
        """Each input's non_witness_utxo to the signer, from the parser's copy of the PSBT at `at`."""
        prevtxs = []
        for i in range(self.plan[PLAN_N_INPUTS]):
            n, off = P.parser_prevtx_len(i), at + P.parser_prevtx_off(i)
            # A view, not a copy: an exchange's batch payout alone can be tens of KB
            prevtxs.append(memoryview(P.memory)[off:off + n] if n else None)
        S.set_prevtxs(prevtxs)


    def sign(self) -> bytes:
        """The signed psbt trimmed, as upstream trims: the unsigned transaction and the signatures."""
        if self.unverified_change:
            raise BitwasmError("multisig change not verified against its descriptor")
        P = _load_parser()
        if self._review() != self.display:
            raise BitwasmError("the transaction changed after it was reviewed")
        S = use(self.seed)
        nonces = bytes(memoryview(P.memory)[P.parser_nonces():P.parser_nonces() + MAX_INPUTS * NONCE_SIZE])
        try:
            sigs = S.sign(nonces)
        except SignerError as e:
            raise BitwasmError(str(e)) from e

        base, points = P.parser_sigs(), P.parser_nonce_points()
        P.memory[points:points + MAX_INPUTS * NONCE_SIZE] = bytes(MAX_INPUTS * NONCE_SIZE)
        for i, sig in enumerate(sigs):
            P.memory[base + i * SIG_SIZE:base + (i + 1) * SIG_SIZE] = sig["raw"]
            if sig["point"]:
                P.memory[points + i * NONCE_SIZE:points + (i + 1) * NONCE_SIZE] = sig["point"]
        n = P.parser_finalize_trimmed(len(sigs))
        if n < 0:
            raise BitwasmError(f"parser: {P_ERRORS.get(-n, -n)}")
        return self.signed_out(memoryview(P.memory)[P.parser_output():P.parser_output() + n])
