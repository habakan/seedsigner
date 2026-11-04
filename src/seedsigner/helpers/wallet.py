"""
Keys and addresses for a Seed, from signer.wasm. The Pico build's replacement for embit_utils.

signer.wasm derives only standard account paths: m/49h, m/84h and m/86h, and m/48h/.../2h, each
with this network's coin type. Anything else raises UnsupportedDerivation.
"""
import hashlib

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



def b58check_decode(s: str) -> bytes:
    n = 0
    for c in s:
        n = n * 58 + _B58.index(c)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
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
