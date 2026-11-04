# SeedSigner's own Seed and wallet code, run as is; prints what CPython must also print
from seedsigner.models.seed import Seed
from seedsigner.models.settings import SettingsConstants as SC
from seedsigner.helpers import wallet, mnemonic_generation

seed = Seed("obscure bone gas open exotic abuse virus bunker shuffle nasty ship dash".split(), passphrase="pass")
print("fingerprint", seed.get_fingerprint())
print("xpub", wallet.account_xpub(seed, "m/84h/0h/0h", SC.MAINNET)["xpub"])
print("xpub48", wallet.account_xpub(seed, "m/48h/1h/0h/2h", SC.TESTNET, SC.MULTISIG)["xpub"])
for net, coin in ((SC.MAINNET, "0h"), (SC.REGTEST, "1h")):
    print("address", net, wallet.address(seed, f"m/86h/{coin}/0h", net, True, 5))
print("message", wallet.sign_message(seed, "m/84h/0h/0h/0/0", SC.MAINNET, b"hello"))
print("bip85", seed.get_bip85_child_mnemonic(0, 12))
print("dice", " ".join(mnemonic_generation.generate_mnemonic_from_dice("3" * 99)))
print("checksum", " ".join(mnemonic_generation.calculate_checksum("abandon " * 11)))
print("word", Seed.get_wordlist()[1234], Seed.get_wordlist().index("zoo"))
