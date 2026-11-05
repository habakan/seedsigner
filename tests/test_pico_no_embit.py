import subprocess
import sys

# Modules already moved to signer.wasm; the Pico build has no embit. See docs/pico.md
NO_EMBIT = [
    "seedsigner.helpers.bitwasm",
    "seedsigner.helpers.mnemonic_generation",
    "seedsigner.helpers.wallet",
    "seedsigner.models.seed",
    "seedsigner.models.psbt",
    "seedsigner.models.psbt_wasm",
    "seedsigner.models.decode_qr",
    "seedsigner.models.encode_qr",
]


def test_imports_without_embit():
    code = "import sys; sys.modules['embit'] = None\n" + "".join(f"import {m}\n" for m in NO_EMBIT) + (
        "from seedsigner.models.seed import Seed\n"
        "s = Seed(('abandon ' * 11 + 'about').split())\n"
        "assert s.get_fingerprint() == '73c5da0a', s.get_fingerprint()\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_multisig_descriptor_without_embit():
    """A descriptor QR is read, registered with a seed of ours and gives its addresses with embit gone."""
    from psbt_testing_util import PSBTTestData
    code = "import sys; sys.modules['embit'] = None\n" + (
        "from seedsigner.models.decode_qr import DecodeQR, DecodeQRStatus\n"
        "from seedsigner.models.seed import Seed\n"
        "from seedsigner.helpers import wallet\n"
        f"d = DecodeQR(); assert d.add_data({PSBTTestData.MULTISIG_NATIVE_SEGWIT_DESCRIPTOR!r}) == DecodeQRStatus.COMPLETE\n"
        "assert d.is_wallet_descriptor\n"
        "m = wallet.Multisig(d.get_wallet_descriptor())\n"
        f"assert m.register([Seed({' '.join(PSBTTestData.seed.mnemonic_list)!r}.split())], 'R')\n"
        "assert wallet.multisig_policy(m)[:2] == ('2', '3')\n"
        "assert wallet.multisig_address(m, 0, False, 'R').startswith('bcrt1q')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
