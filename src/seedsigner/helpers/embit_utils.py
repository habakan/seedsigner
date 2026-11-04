import embit

from binascii import b2a_base64
from hashlib import sha256

from embit import bip32, compact, ec
from embit.bip32 import HDKey
from embit.descriptor import Descriptor
from embit.networks import NETWORKS
from embit.util import secp256k1


from seedsigner.models.settings_definition import SettingsConstants
# Moved to wallet, which needs no embit; kept importable here
from seedsigner.helpers.wallet import get_embit_network_name, get_standard_derivation_path, parse_derivation_path


"""
    Collection of generic embit-powered util methods.
"""
# TODO: PR these directly into `embit`? Or replace with new/existing methods already in `embit`?



def get_xpub(seed_bytes, derivation_path: str, embit_network: str = "main") -> HDKey:
    root = bip32.HDKey.from_seed(seed_bytes, version=NETWORKS[embit_network]["xprv"])
    xprv = root.derive(derivation_path)
    xpub = xprv.to_public()
    return xpub



def get_single_sig_address(xpub: HDKey, script_type: str = SettingsConstants.NATIVE_SEGWIT, index: int = 0, is_change: bool = False, embit_network: str = "main") -> str:
    if is_change:
        pubkey = xpub.derive([1,index]).key
    else:
        pubkey = xpub.derive([0,index]).key

    if script_type == SettingsConstants.LEGACY_P2PKH:
        return embit.script.p2pkh(pubkey).address(network=NETWORKS[embit_network])

    elif script_type == SettingsConstants.NESTED_SEGWIT:
        return embit.script.p2sh(embit.script.p2wpkh(pubkey)).address(network=NETWORKS[embit_network])

    elif script_type == SettingsConstants.NATIVE_SEGWIT:
        return embit.script.p2wpkh(pubkey).address(network=NETWORKS[embit_network])

    elif script_type == SettingsConstants.TAPROOT:
        return embit.script.p2tr(pubkey).address(network=NETWORKS[embit_network])



def get_multisig_address(descriptor: Descriptor, index: int = 0, is_change: bool = False, embit_network: str = "main"):
    if is_change:
        branch_index = 1
    else:
        branch_index = 0

    # Can derive p2wsh, p2sh-p2wsh, and legacy (non-segwit) p2sh
    if descriptor.is_segwit or (descriptor.is_legacy and descriptor.is_basic_multisig):
        return descriptor.derive(index, branch_index=branch_index).script_pubkey().address(network=NETWORKS[embit_network])

    elif descriptor.is_taproot:
        # TODO: Not yet implemented!
        raise Exception("Taproot verification not yet implemented!")

    raise Exception(f"{descriptor.script_pubkey().script_type()} address verification not yet implemented!")



def get_multisig_policy(descriptor: Descriptor) -> tuple:
    """Extract (threshold, n) from a basic multisig descriptor."""
    if not descriptor.is_basic_multisig:
        raise ValueError(f"Expected a basic multisig descriptor, got: {descriptor.brief_policy}")
    return (str(descriptor.miniscript.args[0]), str(len(descriptor.keys)))



def sign_message(seed_bytes: bytes, derivation: str, msg: bytes, compressed: bool = True, embit_network: str = "main") -> bytes:
    """
        from: https://github.com/cryptoadvance/specter-diy/blob/b58a819ef09b2bca880a82c7e122618944355118/src/apps/signmessage/signmessage.py
    """
    """Sign message with private key"""
    msghash = sha256(
        sha256(
            b"\x18Bitcoin Signed Message:\n" + compact.to_bytes(len(msg)) + msg
        ).digest()
    ).digest()

    root = bip32.HDKey.from_seed(seed_bytes, version=NETWORKS[embit_network]["xprv"])
    prv = root.derive(derivation).key
    sig = secp256k1.ecdsa_sign_recoverable(msghash, prv._secret)
    flag = sig[64]
    sig = ec.Signature(sig[:64])
    c = 4 if compressed else 0
    flag = bytes([27 + flag + c])
    ser = flag + secp256k1.ecdsa_signature_serialize_compact(sig._sig)
    return b2a_base64(ser).strip().decode()
