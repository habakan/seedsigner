"""
Review and signing through bitwasm-signer's parser.wasm and signer.wasm, on WAMR.

embit still reads the psbt for the screens, but nothing is signed unless signer.wasm's own
review of the same bytes agrees with it, and only signer.wasm signs. See
PSBTParser._check_with_bitwasm for what has to agree.

Seeds are derived inside signer.wasm. It holds one key at a time: the seed last passed to use().

The modules are bitwasm-signer d4b970a's build/parser.wasm and build/signer.wasm, pinned
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

PARSER_SHA256 = "4a5c16b42ebb958a84063386511daf6dd0ed39d4cd5a20aba1c76047c2841e5f"
SIGNER_SHA256 = "3be85e82fabe05765e63bb35c03d94daa4f6d25a61ea5449623de713fd196517"

OWNER_EXTERNAL, OWNER_CHANGE, OWNER_SELF = 0, 1, 2
TEXT_KIND_OP_RETURN = 1

P_ERRORS = {1: "MAGIC", 2: "FORMAT", 3: "DUPLICATE", 4: "TX", 5: "UNSUPPORTED", 6: "LIMIT", 7: "UTXO", 8: "SIG"}

_parser = None
_signer = None
_active = None



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
    if _parser is None:
        wasm = _read("parser.wasm")
        if hashlib.sha256(wasm).digest().hex() != PARSER_SHA256:
            raise BitwasmError("parser.wasm is not the pinned build")
        _parser = Instance(wasm)
    return _parser



def _load_signer() -> Signer:
    global _signer
    if _signer is None:
        if sys.implementation.name == "micropython":
            _signer = _NativeSigner().init()
        else:
            _signer = Signer(_read("signer.wasm"), sha256=SIGNER_SHA256).init()
    return _signer



def use(seed, network: str = None) -> Signer:
    """
    signer.wasm with `seed`'s key loaded, deriving it only when another seed was loaded last.
    A network re-inits the module, which keeps the key but drops any review or multisig wallet.
    """
    global _active
    S = _load_signer()
    if _active is not seed:
        _active = None
        seed.load_into(S)
        _active = seed
    if network is not None:
        S.init(testnet=network != SettingsConstants.MAINNET)
    return S



def signer() -> Signer:
    """signer.wasm for what needs no key: new mnemonics and SeedQRs."""
    return _load_signer()



def forget(seed=None):
    """Unloads the key, or only `seed`'s when given."""
    global _active
    if seed is None or _active is seed:
        _active = None
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
        lo, hi = 0, 2048
        while lo < hi:
            mid = (lo + hi) // 2
            if self[mid] < word:
                lo = mid + 1
            else:
                hi = mid
        if lo < 2048 and self[lo] == word:
            return lo
        raise ValueError(f"{word!r} is not in the dictionary")

    def __contains__(self, word):
        try:
            self.index(word)
            return True
        except (ValueError, TypeError):
            return False



class BitwasmReview:
    """
    signer.wasm's review of one psbt for one seed: `display` is what it would sign.

    sign() parses and reviews the same bytes again and refuses unless the display is
    unchanged, so what was compared with the screens is what gets signed.
    """
    def __init__(self, psbt_bytes: bytes, seed, network: str, multisig_descriptor: str | None = None):
        self.psbt_bytes = bytes(psbt_bytes)
        self.seed = seed
        self.network = network
        self.multisig_descriptor = multisig_descriptor
        self.wallet_registered = False
        self.display = self._review()


    def _review(self) -> dict:
        P = _load_parser()
        S = use(self.seed, self.network)

        self.wallet_registered = False
        if self.multisig_descriptor:
            try:
                S.multisig_load(self.multisig_descriptor)
                self.wallet_registered = True
            except SignerError as e:
                # Its change is then shown as external, as without a descriptor
                logger.info(f"signer.wasm did not register the descriptor: {e}")

        if len(self.psbt_bytes) > P.parser_input_cap():
            raise BitwasmError("PSBT too large")
        at = P.parser_input()
        P.memory[at:at + len(self.psbt_bytes)] = self.psbt_bytes
        rc = P.parser_parse(len(self.psbt_bytes), int(S.fingerprint, 16))
        if rc != 0:
            raise BitwasmError(f"parser: {P_ERRORS.get(rc, rc)}")

        plan = bytes(P.memory[P.parser_plan():P.parser_plan() + PLAN_SIZE])
        prevtxs = []
        for i in range(plan[PLAN_N_INPUTS]):
            n, off = P.parser_prevtx_len(i), at + P.parser_prevtx_off(i)
            prevtxs.append(bytes(P.memory[off:off + n]) if n else None)
        S.set_plan(plan).set_prevtxs(prevtxs)
        try:
            S.review()
            return S.display()
        except SignerError as e:
            raise BitwasmError(str(e)) from e


    def sign(self) -> bytes:
        """The signed psbt as parser.wasm writes it."""
        P = _load_parser()
        if self._review() != self.display:
            raise BitwasmError("the transaction changed after it was reviewed")
        S = use(self.seed)
        nonces = bytes(P.memory[P.parser_nonces():P.parser_nonces() + MAX_INPUTS * NONCE_SIZE])
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
        n = P.parser_finalize(len(sigs))
        if n < 0:
            raise BitwasmError(f"parser: {P_ERRORS.get(-n, -n)}")
        return bytes(P.memory[P.parser_output():P.parser_output() + n])
