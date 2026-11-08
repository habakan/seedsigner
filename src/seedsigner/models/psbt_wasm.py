"""
PSBTParser's answers from parser.wasm and the signer alone, for the Pico build, which has no embit.

The signer re-derives every key it calls ours, so an output it marks change or self is proven at the
plan's path: that path is `verified_derivation_path`. P2WSH change is the psbt's claim, as embit's parser
has it, until verify_multisig_output() registers the descriptor and the signer re-derives it.
"""
import hashlib
import struct

from seedsigner.helpers import bitwasm, wallet
from seedsigner.models.psbt_errors import (PSBTBitwasmRefusedError, PSBTInputAmountVerificationError,
    PSBTInputOwnershipClaimError, PSBTMalformedOpReturnError, PSBTMissingInputUtxoError, PSBTNegativeFeeError,
    PSBTSeedCannotSignError)
from seedsigner.models.settings import SettingsConstants

P = bitwasm



# RIPEMD-160's message word order and rotations, the left line's 80 steps then the right's
_RMD_W = bytes([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 7, 4, 13, 1, 10, 6, 15, 3, 12, 0, 9, 5, 2, 14,
    11, 8, 3, 10, 14, 4, 9, 15, 8, 1, 2, 7, 0, 6, 13, 11, 5, 12, 1, 9, 11, 10, 0, 8, 12, 4, 13, 3, 7, 15, 14, 5, 6,
    2, 4, 0, 5, 9, 7, 12, 2, 10, 14, 1, 3, 8, 11, 6, 15, 13, 5, 14, 7, 0, 9, 2, 11, 4, 13, 6, 15, 8, 1, 10, 3, 12, 6,
    11, 3, 7, 0, 13, 5, 10, 14, 15, 8, 12, 4, 9, 1, 2, 15, 5, 1, 3, 7, 14, 6, 9, 11, 8, 12, 2, 10, 0, 4, 13, 8, 6, 4,
    1, 3, 11, 15, 0, 5, 12, 2, 13, 9, 7, 10, 14, 12, 15, 10, 4, 1, 5, 8, 7, 6, 2, 13, 14, 0, 3, 9, 11])
_RMD_S = bytes([11, 14, 15, 12, 5, 8, 7, 9, 11, 13, 14, 15, 6, 7, 9, 8, 7, 6, 8, 13, 11, 9, 7, 15, 7, 12, 15, 9, 11,
    7, 13, 12, 11, 13, 6, 7, 14, 9, 13, 15, 14, 8, 13, 6, 5, 12, 7, 5, 11, 12, 14, 15, 14, 15, 9, 8, 9, 14, 5, 6, 8,
    6, 5, 12, 9, 15, 5, 11, 6, 8, 13, 12, 5, 12, 13, 14, 11, 8, 5, 6, 8, 9, 9, 11, 13, 15, 15, 5, 7, 7, 8, 11, 14,
    14, 12, 6, 9, 13, 15, 7, 12, 8, 9, 11, 7, 7, 12, 7, 6, 15, 13, 11, 9, 7, 15, 11, 8, 6, 6, 14, 12, 13, 5, 14, 13,
    13, 7, 5, 15, 5, 8, 11, 14, 14, 6, 14, 6, 9, 12, 9, 12, 5, 15, 8, 8, 5, 12, 9, 12, 5, 14, 6, 8, 13, 6, 5, 15, 13,
    11, 11])
_RMD_K = (0, 0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xA953FD4E, 0x50A28BE6, 0x5C4DD124, 0x6D703EF3, 0x7A6D76E9, 0)


def _hash160(data: bytes) -> bytes:
    # RIPEMD-160 of SHA-256, here because the Pico's hashlib has no RIPEMD-160
    M = 0xFFFFFFFF
    f = (lambda x, y, z: x ^ y ^ z, lambda x, y, z: (x & y) | (~x & z), lambda x, y, z: (x | ~y) ^ z,
         lambda x, y, z: (x & z) | (y & ~z), lambda x, y, z: x ^ (y | ~z))
    m = hashlib.sha256(data).digest() + b"\x80" + bytes(23) + struct.pack("<Q", 256)
    h = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0]
    x = struct.unpack("<16I", m)
    lines = []
    for side in (0, 1):
        a, b, c, d, e = h
        for j in range(80):
            r = j // 16
            t = (a + f[4 - r if side else r](b, c, d) + x[_RMD_W[80 * side + j]] + _RMD_K[5 * side + r]) & M
            s = _RMD_S[80 * side + j]
            a, b, c, d, e = e, (((t << s) | (t >> (32 - s))) + e) & M, b, (c << 10 | c >> 22) & M, d
        lines.append((a, b, c, d, e))
    (a1, b1, c1, d1, e1), (a2, b2, c2, d2, e2) = lines
    h = [(h[1] + c1 + d2) & M, (h[2] + d1 + e2) & M, (h[3] + e1 + a2) & M, (h[4] + a1 + b2) & M, (h[0] + b1 + c2) & M]
    return struct.pack("<5I", *h)



def _keypath(plan: bytes, at: int) -> list:
    depth = plan[at]
    return list(struct.unpack_from("<%dI" % depth, plan, at + 8)) if depth else []



def _policy(spk: bytes, wscript: bytes) -> dict:
    """The inputs' policy in embit's terms, from the scriptPubKey of an input the seed signs."""
    if len(spk) == 22 and spk[:2] == b"\x00\x14":
        return {"type": "p2wpkh"}
    if len(spk) == 34 and spk[:2] == b"\x51\x20":
        return {"type": "p2tr"}
    if len(spk) == 25 and spk[:3] == b"\x76\xa9\x14":
        return {"type": "p2pkh"}
    if len(spk) == 23 and spk[:2] == b"\xa9\x14" and not wscript:
        return {"type": "p2sh-p2wpkh"}
    if (len(spk) == 34 and spk[:2] == b"\x00\x20" or len(spk) == 23) and wscript:
        # A P2SH's is P2SH-P2WSH's witness script, or BIP45's redeem script, which hashes to the P2SH itself
        kind = "p2wsh" if len(spk) == 34 else "p2sh" if _hash160(wscript) == spk[2:22] else "p2sh-p2wsh"
        if wscript[-1] == 0xae and 0x51 <= wscript[0] <= 0x60:  # OP_m <keys> OP_n OP_CHECKMULTISIG
            return {"type": kind, "m": wscript[0] - 0x50, "n": wscript[-2] - 0x50}
        return {"type": kind}  # Liana's or_d, which SeedSigner shows as single key
    return None



def _op_return(spk: bytes) -> bytes:
    """The pushes after OP_RETURN, joined, as PSBTParser._parse_op_return_payload reads them (it needs embit's
    module): opcodes up to OP_16 that push no data are kept as they are, and anything else is refused."""
    out, i = b"", 1
    while i < len(spk):
        op = spk[i]
        size = {0x4c: 1, 0x4d: 2, 0x4e: 4}.get(op, 0)
        if not (1 <= op <= 0x4b or size):
            if op > 0x60:
                raise PSBTMalformedOpReturnError("OP_RETURN script holds non-push opcode 0x%02x" % op)
            out, i = out + spk[i:i + 1], i + 1
            continue
        if i + 1 + size > len(spk):
            raise PSBTMalformedOpReturnError("OP_RETURN push length field is truncated")
        n = int.from_bytes(spk[i + 1:i + 1 + size], "little") if size else op
        if i + 1 + size + n > len(spk):
            raise PSBTMalformedOpReturnError("OP_RETURN push runs past the end of the script")
        out, i = out + spk[i + 1 + size:i + 1 + size + n], i + 1 + size + n
    return bytes(out)


# The modules' refusals that upstream's PSBTParser has its own error for, so the Pico shows the same screen.
# NOT_OURS also covers a P2WSH input whose witness script is not its own, which upstream calls an attack
_REFUSALS = {"parser: UTXO": PSBTMissingInputUtxoError, "parser: UTXO_MISMATCH": PSBTInputAmountVerificationError,
             "review: PREVTX_MISMATCH": PSBTInputAmountVerificationError, "review: FEE": PSBTNegativeFeeError,
             "review: PREVTX_MISSING": PSBTInputAmountVerificationError,
             "review: NOT_OURS": PSBTInputOwnershipClaimError, "review: OP_RETURN": PSBTMalformedOpReturnError}



class WasmPSBTParser:
    HIGH_FEES_WARNING_THRESHOLD = 25

    def __init__(self, p, seed, network: str = SettingsConstants.MAINNET, psbt_bytes: bytes = None, multisig_descriptor=None):
        # `p` is embit's PSBT where there is one; the bytes are what the modules read
        if psbt_bytes is None and not isinstance(p, (bytes, bytearray)) and not hasattr(p, "chunks"):
            psbt_bytes = p.serialize()
        self.psbt_bytes = P.as_psbt(psbt_bytes if psbt_bytes is not None else p)
        self.seed = seed
        self.network = network
        self.multisig_descriptor = multisig_descriptor
        self.bitwasm_review = None
        self.policy = None
        self.spend_amount = 0
        self.change_amount = 0
        self.change_data = []
        self.fee_amount = 0
        self.verified_input_amount = 0
        self.num_inputs = 0
        self.destination_addresses = []
        self.destination_amounts = []
        self.op_return_data = None
        self.op_return_amount = 0
        self.is_high_fee = False
        if self.seed is not None:
            self.parse()


    def parse(self):
        try:
            r = P.BitwasmReview(self.psbt_bytes, self.seed, self.network,
                                str(self.multisig_descriptor) if self.multisig_descriptor else None)
        except P.BitwasmError as e:
            if "NOTHING_TO_SIGN" in str(e):
                raise PSBTSeedCannotSignError() from e
            raise _REFUSALS.get(str(e), PSBTBitwasmRefusedError)(str(e)) from e
        self.bitwasm_review = r
        plan, shown, review = r.plan, r.display, r.review

        self.num_inputs = plan[P.PLAN_N_INPUTS]
        self.verified_input_amount = review["total_in"]
        self.fee_amount = shown["fee"]
        for i in range(self.num_inputs):
            if review["will_sign"][i]:
                at = P.PLAN_INPUTS + i * P.PLAN_INPUT_SIZE + P.PLAN_IN_SPK
                ws = P.PLAN_WSCRIPTS + i * P.PLAN_WSCRIPT_SIZE
                n = plan[ws] | plan[ws + 1] << 8  # a 2-byte length since plan version 4
                self.policy = _policy(plan[at + 1:at + 1 + plan[at]], plan[ws + 2:ws + 2 + n])
                break

        for i, out in enumerate(shown["outputs"]):
            at = P.PLAN_OUTPUTS + i * P.PLAN_OUTPUT_SIZE
            if out["text_kind"] == P.TEXT_KIND_OP_RETURN:
                spk = plan[at + P.PLAN_OUT_SPK + 1:at + P.PLAN_OUT_SPK + 1 + plan[at + P.PLAN_OUT_SPK]]
                self.op_return_data = _op_return(spk)
                self.op_return_amount += out["amount"]
                continue
            address = wallet.for_network(out["text"], self.network)
            if out["owner"] != P.OWNER_EXTERNAL or self._claims_multisig_change(plan, at, r):
                self.change_data.append({
                    "output_index": i,
                    "address": address,
                    "amount": out["amount"],
                    "verified_derivation_path": _keypath(plan, at + P.PLAN_OUT_KEY),
                })
                self.change_amount += out["amount"]
            else:
                self.destination_addresses.append(address)
                self.destination_amounts.append(out["amount"])
                self.spend_amount += out["amount"]

        # Upstream checks a claim against the output's witness script, which the plan does not carry: so unproven, it
        # is shown as change, as there, but signed only once verify_multisig_output() proves it
        r.unverified_change = any(out["owner"] == P.OWNER_EXTERNAL for out in (shown["outputs"][c["output_index"]]
                                                                              for c in self.change_data))
        self.is_high_fee = self.has_high_fee()
        return True


    def get_change_data(self, change_num: int) -> dict:
        if change_num < len(self.change_data):
            return self.change_data[change_num]


    @property
    def num_change_outputs(self):
        return len(self.change_data)


    @property
    def is_multisig(self):
        return self.policy is not None and "m" in self.policy


    @property
    def num_destinations(self):
        return len(self.destination_addresses)


    def _claims_multisig_change(self, plan, at, review) -> bool:
        """A P2WSH (or P2SH) output the psbt says is this seed's, before any descriptor can say whether it is."""
        spk, key = at + P.PLAN_OUT_SPK, at + P.PLAN_OUT_KEY
        wrapped = (plan[spk] == 34 and plan[spk + 1:spk + 3] == b"\x00\x20") if self.policy["type"] == "p2wsh" else plan[spk] == 23
        return (not review.wallet_registered and self.is_multisig and wrapped
                and plan[key] and struct.unpack_from("<I", plan, key + 4)[0] == int(bitwasm.use(self.seed).fingerprint, 16))


    def verify_multisig_output(self, descriptor, change_num: int) -> bool:
        """Whether the signer, with `descriptor` registered, re-derives this change output as ours."""
        if change_num >= len(self.change_data):
            return False
        if not self.bitwasm_review.wallet_registered or str(descriptor) != str(self.multisig_descriptor):
            try:
                r = P.BitwasmReview(self.psbt_bytes, self.seed, self.network, str(descriptor))
            except P.BitwasmError:
                return False
            if not r.wallet_registered:
                return False
            self.bitwasm_review, self.multisig_descriptor = r, descriptor
        out = self.bitwasm_review.display["outputs"][self.change_data[change_num]["output_index"]]
        return out["owner"] != P.OWNER_EXTERNAL


    @staticmethod
    def is_change_branch(derivation_path: list) -> bool:
        return len(derivation_path) >= 2 and derivation_path[-2] == 1


    @staticmethod
    def has_matching_input_fingerprint(psbt, seed, network: str = SettingsConstants.MAINNET) -> bool:
        raw = psbt if isinstance(psbt, (bytes, bytearray)) or hasattr(psbt, "chunks") else psbt.serialize()
        return P.plan_fingerprints(raw, int(seed.get_fingerprint(network), 16))


    def has_high_fee(self) -> bool:
        """As PSBTParser: the fee against all outputs but true change (self-transfers count as sent)."""
        true_change = sum(c["amount"] for c in self.change_data if self.is_change_branch(c["verified_derivation_path"]))
        total = self.spend_amount + self.change_amount + self.op_return_amount - true_change
        return total > 0 and self.fee_amount > (self.HIGH_FEES_WARNING_THRESHOLD / 100) * total
