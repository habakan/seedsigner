import pytest

from seedsigner.helpers import embit_utils, wallet
from seedsigner.models.seed import Seed
from seedsigner.models.settings_definition import SettingsConstants as SC


SEED = Seed("obscure bone gas open exotic abuse virus bunker shuffle nasty ship dash".split(), passphrase="pass")
MESSAGES = [b"hello", b"Chancellor on brink of second bailout for banks", b"x" * wallet.MESSAGE_MAX]


@pytest.mark.parametrize("network,coin", [(SC.MAINNET, "0h"), (SC.TESTNET, "1h"), (SC.REGTEST, "1h")])
@pytest.mark.parametrize("path", ["m/84h/{}/0h/0/0", "m/84h/{}/3h/1/7", "m/49h/{}/0h/0/2"])
def test_sign_message_matches_embit(network, coin, path):
    """signer.wasm's signature, given SeedSigner's header, is the bytes embit made."""
    path = path.format(coin)
    embit_network = embit_utils.get_embit_network_name(network)
    for message in MESSAGES:
        expected = embit_utils.sign_message(SEED.seed_bytes, path, message, embit_network=embit_network)
        assert wallet.sign_message(SEED, path, network, message) == expected

    details = wallet.parse_derivation_path(path)
    xpub = SEED.get_xpub(details["wallet_derivation_path"], network=network)
    expected = embit_utils.get_single_sig_address(xpub, details["script_type"], details["index"], details["is_change"], embit_network)
    assert wallet.message_address(SEED, path, network, b"hello") == expected


@pytest.mark.parametrize("path,network", [
    ("m/44h/0h/0h/0/0", SC.MAINNET),   # legacy
    ("m/86h/0h/0h/0/0", SC.MAINNET),   # taproot has no BIP137 form
    ("m/84h/1h/0h/0/0", SC.MAINNET),   # coin type of another network
    ("m/84h/0h/0h/2/0", SC.MAINNET),   # not a receive or change chain
    ("m/84h/0h/0h", SC.MAINNET),       # an account, not an address
])
def test_sign_message_refuses_what_signer_wasm_does_not_sign(path, network):
    with pytest.raises(wallet.UnsupportedDerivation):
        wallet.sign_message(SEED, path, network, b"hello")
