"""
Keys and addresses for a Seed, from signer.wasm. The Pico build's replacement for embit_utils.

signer.wasm derives only standard account paths: m/49h, m/84h and m/86h, and m/48h/.../2h, each
with this network's coin type. Anything else raises UnsupportedDerivation.
"""
import hashlib

from binascii import b2a_base64

from seedsigner.helpers import bitwasm
from seedsigner.models.settings_definition import SettingsConstants

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# SLIP-132 versions by (purpose, multisig script); testnet and regtest share one set
_VERSIONS = {
    "main": {"xpub": "0488b21e", "ypub": "049d7cb2", "zpub": "04b24746", "Ypub": "0295b43f", "Zpub": "02aa7ed3"},
    "test": {"xpub": "043587cf", "ypub": "044a5262", "zpub": "045f1cf6", "Ypub": "024289ef", "Zpub": "02575483"},
}



class UnsupportedDerivation(Exception):
    pass



# TODO: Refactor `wallet_type` to conform to our `sig_type` naming convention
def get_standard_derivation_path(network: str = SettingsConstants.MAINNET, wallet_type: str = SettingsConstants.SINGLE_SIG, script_type: str = SettingsConstants.NATIVE_SEGWIT) -> str:
    if network == SettingsConstants.MAINNET:
        network_path = "0'"
    elif network == SettingsConstants.TESTNET:
        network_path = "1'"
    elif network == SettingsConstants.REGTEST:
        network_path = "1'"
    else:
        raise Exception("Unexpected network")

    if wallet_type == SettingsConstants.SINGLE_SIG:
        if script_type == SettingsConstants.LEGACY_P2PKH:
            return f"m/44'/{network_path}/0'"
        elif script_type == SettingsConstants.NESTED_SEGWIT:
            return f"m/49'/{network_path}/0'"
        elif script_type == SettingsConstants.NATIVE_SEGWIT:
            return f"m/84'/{network_path}/0'"
        elif script_type == SettingsConstants.TAPROOT:
            return f"m/86'/{network_path}/0'"
        else:
            raise Exception("Unexpected script type")

    elif wallet_type == SettingsConstants.MULTISIG:
        if script_type == SettingsConstants.LEGACY_P2PKH:
            return f"m/45'" #BIP-45
        elif script_type == SettingsConstants.NESTED_SEGWIT:
            return f"m/48'/{network_path}/0'/1'"
        elif script_type == SettingsConstants.NATIVE_SEGWIT:
            return f"m/48'/{network_path}/0'/2'"
        elif script_type == SettingsConstants.TAPROOT:
            raise Exception("Taproot multisig not yet supported")
        else:
            raise Exception("Unexpected script type")
    else:
        raise Exception("Unexpected wallet type")    # checks that all inputs are from the same wallet



def get_embit_network_name(settings_name):
    """ Convert SeedSigner SettingsConstants for `network` to embit's NETWORK key """
    lookup = {
        SettingsConstants.MAINNET: "main",
        SettingsConstants.TESTNET: "test",
        SettingsConstants.REGTEST: "regtest",
    }
    return lookup.get(settings_name)



def parse_derivation_path(derivation_path: str) -> dict:
    """
    Parses a derivation path into its related SettingsConstants equivalents.

    Primarily only supports single sig derivation paths.

    May return None for fields it cannot parse.
    """
    # Support either m/44'/... or m/44h/... style
    derivation_path = derivation_path.replace("'", "h")

    sections = derivation_path.split("/")

    if sections[1] == "48h":
        # So far this helper is only meant for single sig message signing
        raise Exception("Not implemented")

    lookups = {
        "script_types": {
            "44h": SettingsConstants.LEGACY_P2PKH,
            "49h": SettingsConstants.NESTED_SEGWIT,
            "84h": SettingsConstants.NATIVE_SEGWIT,
            "86h": SettingsConstants.TAPROOT,
        },
        "networks": {
            "0h": SettingsConstants.MAINNET,
            "1h": [SettingsConstants.TESTNET, SettingsConstants.REGTEST],
        }
    }

    details = dict()
    details["script_type"] = lookups["script_types"].get(sections[1])
    if not details["script_type"]:
        details["script_type"] = SettingsConstants.CUSTOM_DERIVATION
    details["network"] = lookups["networks"].get(sections[2])

    # Check if there's a standard change path
    if sections[-2] in ["0", "1"]:
        details["is_change"] = sections[-2] == "1"
    else:
        details["is_change"] = None

    # Check if there's a standard address index
    if sections[-1].isdigit():
        details["index"] = int(sections[-1])
    else:
        details["index"] = None

    if details["is_change"] is not None and details["index"] is not None:
        # standard change and addr index; safe to truncate to the wallet level
        details["wallet_derivation_path"] = "/".join(sections[:-2])
    else:
        details["wallet_derivation_path"] = None

    details["clean_match"] = True
    for k, v in details.items():
        if v is None:
            # At least one field couldn't be parsed
            details["clean_match"] = False
            break

    return details



def b58check_decode(s: str) -> bytes:
    n = 0
    for c in s:
        n = n * 58 + _B58.index(c)
    raw = b""
    while n:  # MicroPython's int has no bit_length()
        n, r = divmod(n, 256)
        raw = bytes([r]) + raw
    raw = bytes(len(s) - len(s.lstrip("1"))) + raw
    payload, checksum = raw[:-4], raw[-4:]
    if hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] != checksum:
        raise ValueError("bad base58 checksum")
    return payload



def b58check_encode(payload: bytes) -> str:
    raw = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n, out = int.from_bytes(raw, "big"), ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    return "1" * (len(raw) - len(raw.lstrip(b"\0"))) + out



def version_name(derivation_path: str, sig_type: str = SettingsConstants.SINGLE_SIG) -> str:
    """embit's bip32.detect_version, by name: zpub for 84h, ypub for 49h, Zpub/Ypub for 48h/.../2h or 1h."""
    parts = derivation_path.replace("'", "h").split("/")
    purpose = parts[1] if len(parts) > 1 else ""
    if purpose == "84h":
        return "zpub"
    if purpose == "49h":
        return "ypub"
    if purpose == "48h" and len(parts) > 4:
        return {"2h": "Zpub", "1h": "Ypub"}.get(parts[4], "xpub")
    return "xpub"



def version_bytes(name: str, network: str = SettingsConstants.MAINNET) -> bytes:
    return bytes.fromhex(_VERSIONS["main" if network == SettingsConstants.MAINNET else "test"][name])



def standard_account(derivation_path: str, network: str) -> tuple:
    """(purpose, account) for a path signer.wasm derives, or UnsupportedDerivation."""
    coin = "0h" if network == SettingsConstants.MAINNET else "1h"
    parts = derivation_path.replace("'", "h").rstrip("/").split("/")
    ok = (len(parts) == 4 and parts[1] in ("49h", "84h", "86h")) or (len(parts) == 5 and parts[1] == "48h" and parts[4] == "2h")
    if ok and parts[0] == "m" and parts[2] == coin and parts[3].endswith("h") and parts[3][:-1].isdigit():
        return int(parts[1][:-1]), int(parts[3][:-1])
    raise UnsupportedDerivation(f"signer.wasm does not derive {derivation_path} on {network}")



def account_xpub(seed, derivation_path: str, network: str, sig_type: str = SettingsConstants.SINGLE_SIG) -> dict:
    """
    The account xpub at a standard path. `xpub` is in the version SeedSigner shows (SLIP-132),
    `raw` is the 78-byte serialization and `fingerprint` the master's, as hex.
    """
    purpose, account = standard_account(derivation_path, network)
    S = bitwasm.use(seed, network)
    raw = b58check_decode(S.xpub(purpose, account)["xpub"])
    version = seed.detect_version(derivation_path, network, sig_type)
    raw = version + raw[4:]
    return {"xpub": b58check_encode(raw), "raw": raw, "fingerprint": S.fingerprint}



_BECH32 = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"



def _polymod(values) -> int:
    chk = 1
    for v in values:
        top = chk >> 25
        chk = (chk & 0x1ffffff) << 5 ^ v
        for i, g in enumerate((0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3)):
            chk ^= g if (top >> i) & 1 else 0
    return chk



def _hrp_values(hrp: str) -> list:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]



def for_network(address: str, network: str) -> str:
    """
    signer.wasm knows mainnet and testnet; regtest's segwit addresses differ only in their bech32
    prefix (its P2SH ones are testnet's), so `tb1` is rewritten as `bcrt1` with a new checksum.
    """
    if network != SettingsConstants.REGTEST or not address.startswith("tb1"):
        return address
    data = [_BECH32.index(c) for c in address[3:]]
    const = _polymod(_hrp_values("tb") + data)
    if const not in (1, 0x2bc830a3):  # bech32, bech32m
        raise ValueError("bad bech32 checksum")
    data = data[:-6]
    chk = _polymod(_hrp_values("bcrt") + data + [0] * 6) ^ const
    return "bcrt1" + "".join(_BECH32[d] for d in data + [(chk >> 5 * (5 - i)) & 31 for i in range(6)])



MESSAGE_MAX = 512  # signer.wasm's limit, in bytes



def _message_key(derivation_path: str, network: str) -> tuple:
    """(purpose, account, chain, index) for m/49h or m/84h single sig addresses."""
    parts = derivation_path.replace("'", "h").split("/")
    if len(parts) == 6 and parts[4] in ("0", "1") and parts[5].isdigit():
        purpose, account = standard_account("/".join(parts[:4]), network)
        if purpose in (49, 84):
            return purpose, account, int(parts[4]), int(parts[5])
    raise UnsupportedDerivation(f"signer.wasm signs messages only for m/49h and m/84h addresses, not {derivation_path}")



def message_address(seed, derivation_path: str, network: str, message: bytes) -> str:
    address = bitwasm.use(seed, network).message_review(message, *_message_key(derivation_path, network))["address"]
    return for_network(address, network)



def sign_message(seed, derivation_path: str, network: str, message: bytes) -> str:
    """Base64, with the header SeedSigner always gave: 31-34, a compressed key whatever the script."""
    S = bitwasm.use(seed, network)
    S.message_review(message, *_message_key(derivation_path, network))
    sig = S.message_sign()
    # signer.wasm writes BIP137's header for the script; the recovery id is its low two bits
    sig = bytes([31 + ((sig[0] - 27) & 3)]) + sig[1:]
    return b2a_base64(sig).strip().decode()



def address(seed, derivation_path: str, network: str, is_change: bool, index: int) -> str:
    """The single sig address at index on the receive or change chain of a standard account path."""
    purpose, account = standard_account(derivation_path, network)
    if purpose == 48:
        raise UnsupportedDerivation("signer.wasm lists single sig addresses only")
    return for_network(bitwasm.use(seed, network).address(purpose, account, int(is_change), index), network)



def path_to_str(path: list) -> str:
    """embit's bip32.path_to_str: m/84h/0h/0h/1/0."""
    return "m" + "".join("/%d%s" % (i & 0x7FFFFFFF, "h" if i & 0x80000000 else "") for i in path)



def _multipath(descriptor: str) -> str:
    """Each key's children as the signer reads them, /<0;1>/*, where SeedSigner writes /{0,1}/*, /0/* or none for
    embit. A checksum no longer fits once a key changes, so it goes then."""
    out, i, n = [], 0, len(descriptor)
    while True:
        j = descriptor.find("]", i)
        if j < 0:
            out.append(descriptor[i:])
            break
        k = j + 1
        while k < n and (descriptor[k].isalpha() or descriptor[k].isdigit()):
            k += 1
        out.append(descriptor[i:k])
        for old in ("/{0,1}/*", "/0/*"):
            if descriptor.startswith(old, k):
                k += len(old)
                out.append("/<0;1>/*")
                break
        else:
            if k < n and descriptor[k] in ",)":
                out.append("/<0;1>/*")
        i = k
    s = "".join(out)
    return s if s == descriptor else s.split("#", 1)[0]



class Multisig:
    """
    A multisig wallet where there is no embit: its descriptor as the signer reads it, and the seed of ours it is
    registered with, as the signer derives its addresses only from one of its own keys.
    """
    def __init__(self, descriptor: str):
        self.descriptor = _multipath(descriptor.strip())
        self.seed = self.info = None


    def register(self, seeds, network: str) -> bool:
        """Registers it with the first of `seeds` it holds a key of; False when none does or the signer cannot read it."""
        for seed in seeds:
            try:
                self.info, self.seed = bitwasm.use_multisig(seed, network, self.descriptor), seed
                return True
            except bitwasm.SignerError:
                pass
        return False


    def address(self, index: int, is_change: bool, network: str) -> str:
        bitwasm.use_multisig(self.seed, network, self.descriptor)
        return for_network(bitwasm.signer().multisig_address(int(is_change), index), network)


    def __str__(self):
        return self.descriptor



def multisig_policy(descriptor) -> tuple:
    """(threshold, n, fingerprints) of embit's Descriptor, or of a Multisig."""
    if isinstance(descriptor, Multisig):
        fingerprints = descriptor.info["fingerprints"]
        return str(descriptor.info["threshold"]), str(len(fingerprints)), fingerprints  # strings, as embit_utils gives
    from binascii import hexlify
    from seedsigner.helpers.embit_utils import get_multisig_policy
    threshold, n = get_multisig_policy(descriptor)
    return threshold, n, [hexlify(key.fingerprint).decode() for key in descriptor.keys]



def multisig_address(descriptor, index: int, is_change: bool, network: str) -> str:
    """The address of embit's Descriptor, or of a Multisig, at index on the receive or change chain."""
    if isinstance(descriptor, Multisig):
        return descriptor.address(index, is_change, network)
    from seedsigner.helpers import embit_utils
    return embit_utils.get_multisig_address(descriptor=descriptor, index=index, is_change=is_change,
                                            embit_network=get_embit_network_name(network))
