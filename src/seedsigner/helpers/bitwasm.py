"""
Review and signing through bitwasm-signer's parser.wasm and signer.wasm, on WAMR.

embit still reads the psbt for the screens, but nothing is signed unless signer.wasm's own
review of the same bytes agrees with it, and only signer.wasm signs. See
PSBTParser._check_with_bitwasm for what has to agree.

The modules are bitwasm-signer 5ae24be's build/parser.wasm and build/signer.wasm, pinned
by hash. libiwasm (WAMR 2.4.5, classic interpreter) comes from the OS image.
"""
import hashlib
import logging
import os

from bitwasm_signer import Instance, Signer, SignerError
from bitwasm_signer.signer import MAX_INPUTS, NONCE_SIZE, PLAN_N_INPUTS, PLAN_SIZE, SIG_SIZE

from seedsigner.models.settings import SettingsConstants

logger = logging.getLogger(__name__)

PARSER_SHA256 = "9407abe3a65a56ebcfcab6da3b685f4e21ce9f6a60b3feddd299ddc0def89bab"
SIGNER_SHA256 = "f1ec4d091292d83f44cd479219914e1b2f080c930867e8086d731bf76deb979c"

OWNER_EXTERNAL, OWNER_CHANGE, OWNER_SELF = 0, 1, 2
TEXT_KIND_OP_RETURN = 1

P_ERRORS = {1: "MAGIC", 2: "FORMAT", 3: "DUPLICATE", 4: "TX", 5: "UNSUPPORTED", 6: "LIMIT", 7: "UTXO", 8: "SIG"}

_modules = None



class BitwasmError(Exception):
    pass



def _load_modules():
    """
    One parser and one signer instance per process, read and hash-checked on first use.
    The signer holds no key between reviews: every path out of it unloads.
    """
    global _modules
    if _modules is None:
        resources = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "bitwasm")
        with open(os.path.join(resources, "parser.wasm"), "rb") as f:
            parser_wasm = f.read()
        with open(os.path.join(resources, "signer.wasm"), "rb") as f:
            signer_wasm = f.read()
        if hashlib.sha256(parser_wasm).hexdigest() != PARSER_SHA256:
            raise BitwasmError("parser.wasm is not the pinned build")
        _modules = (Instance(parser_wasm), Signer(signer_wasm, sha256=SIGNER_SHA256))
    return _modules



class BitwasmReview:
    """
    signer.wasm's review of one psbt for one seed: `display` is what it would sign.

    sign() parses and reviews the same bytes again and refuses unless the display is
    unchanged, so what was compared with the screens is what gets signed.
    """
    def __init__(self, psbt_bytes: bytes, seed_bytes: bytes, network: str, multisig_descriptor: str | None = None):
        self.psbt_bytes = bytes(psbt_bytes)
        self.seed_bytes = bytes(seed_bytes)
        self.network = network
        self.multisig_descriptor = multisig_descriptor
        self.wallet_registered = False
        try:
            self.display = self._review()
        finally:
            _load_modules()[1].unload()


    def _review(self) -> dict:
        P, S = _load_modules()
        S.init(testnet=self.network != SettingsConstants.MAINNET)
        S.load_seed(bytearray(self.seed_bytes))

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
        """The signed psbt as parser.wasm writes it. The key is unloaded either way."""
        P, S = _load_modules()
        try:
            if self._review() != self.display:
                raise BitwasmError("the transaction changed after it was reviewed")
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
        finally:
            S.unload()
