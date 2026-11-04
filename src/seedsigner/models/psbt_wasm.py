"""
PSBTParser's answers from parser.wasm and the signer alone, for the Pico build, which has no embit.

The signer re-derives every key it calls ours, so an output it marks change or self is proven at the
plan's path: that path is `verified_derivation_path`. P2WSH change is external unless the multisig
descriptor registered with the signer; embit's parser would presume it change from the psbt's claims.
"""
import struct

from seedsigner.helpers import bitwasm, wallet
from seedsigner.models.psbt_errors import PSBTBitwasmRefusedError, PSBTSeedCannotSignError
from seedsigner.models.settings import SettingsConstants

P = bitwasm



def _keypath(plan: bytes, at: int) -> list:
    depth = plan[at]
    return list(struct.unpack_from("<%dI" % depth, plan, at + 8)) if depth else []



def _policy(spk: bytes, wscript: bytes) -> dict:
    """The inputs' policy in embit's terms, from the scriptPubKey of an input the seed signs."""
    if len(spk) == 22 and spk[:2] == b"\x00\x14":
        return {"type": "p2wpkh"}
    if len(spk) == 34 and spk[:2] == b"\x51\x20":
        return {"type": "p2tr"}
    if len(spk) == 23 and spk[:2] == b"\xa9\x14":
        return {"type": "p2sh-p2wpkh"}
    if len(spk) == 34 and spk[:2] == b"\x00\x20" and wscript:
        return {"type": "p2wsh", "m": wscript[0] - 0x50, "n": wscript[-2] - 0x50}
    return None



def _op_return(spk: bytes) -> bytes:
    """The payload after OP_RETURN's push, of whichever size."""
    op = spk[1] if len(spk) > 1 else 0
    if op == 0x4c:
        return bytes(spk[3:3 + spk[2]])
    if op == 0x4d:
        return bytes(spk[4:4 + (spk[2] | spk[3] << 8)])
    return bytes(spk[2:2 + op]) if 0 < op < 0x4c else b""



class WasmPSBTParser:
    HIGH_FEES_WARNING_THRESHOLD = 25

    def __init__(self, p, seed, network: str = SettingsConstants.MAINNET, psbt_bytes: bytes = None, multisig_descriptor=None):
        # `p` is embit's PSBT where there is one; the bytes are what the modules read
        self.psbt_bytes = bytes(psbt_bytes) if psbt_bytes is not None else (p if isinstance(p, (bytes, bytearray)) else p.serialize())
        self.seed = seed
        self.network = network
        self.multisig_descriptor = multisig_descriptor
        self.bitwasm_review = None
        self.policy = None
        self.spend_amount = 0
        self.change_amount = 0
        self.change_data = []
        self.fee_amount = 0
        self.input_amount = 0
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
            raise PSBTBitwasmRefusedError(str(e)) from e
        self.bitwasm_review = r
        plan, shown, review = r.plan, r.display, r.review

        self.num_inputs = plan[P.PLAN_N_INPUTS]
        self.input_amount = review["total_in"]
        self.fee_amount = shown["fee"]
        for i in range(self.num_inputs):
            if review["will_sign"][i]:
                at = P.PLAN_INPUTS + i * P.PLAN_INPUT_SIZE + P.PLAN_IN_SPK
                ws = P.PLAN_WSCRIPTS + i * P.PLAN_WSCRIPT_SIZE
                self.policy = _policy(plan[at + 1:at + 1 + plan[at]], plan[ws + 1:ws + 1 + plan[ws]])
                break

        for i, out in enumerate(shown["outputs"]):
            at = P.PLAN_OUTPUTS + i * P.PLAN_OUTPUT_SIZE
            if out["text_kind"] == P.TEXT_KIND_OP_RETURN:
                spk = plan[at + P.PLAN_OUT_SPK + 1:at + P.PLAN_OUT_SPK + 1 + plan[at + P.PLAN_OUT_SPK]]
                self.op_return_data = _op_return(spk)
                self.op_return_amount += out["amount"]
                continue
            address = wallet.for_network(out["text"], self.network)
            if out["owner"] != P.OWNER_EXTERNAL:
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


    def verify_multisig_output(self, descriptor, change_num: int) -> bool:
        # The signer counts P2WSH change only for the wallet it registered from this descriptor
        return self.bitwasm_review.wallet_registered and change_num < len(self.change_data)


    @staticmethod
    def is_change_branch(derivation_path: list) -> bool:
        return len(derivation_path) >= 2 and derivation_path[-2] == 1


    @staticmethod
    def has_matching_input_fingerprint(psbt, seed, network: str = SettingsConstants.MAINNET) -> bool:
        raw = psbt if isinstance(psbt, (bytes, bytearray)) else psbt.serialize()
        return P.plan_fingerprints(bytes(raw), int(seed.get_fingerprint(network), 16))


    def has_high_fee(self) -> bool:
        """As PSBTParser: the fee against all outputs but true change (self-transfers count as sent)."""
        true_change = sum(c["amount"] for c in self.change_data if self.is_change_branch(c["verified_derivation_path"]))
        total = self.spend_amount + self.change_amount + self.op_return_amount - true_change
        return total > 0 and self.fee_amount > (self.HIGH_FEES_WARNING_THRESHOLD / 100) * total
