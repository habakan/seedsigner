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
