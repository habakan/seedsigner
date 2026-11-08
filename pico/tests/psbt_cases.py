"""
PSBTs for BIP39's test seed (abandon x11 about), mainnet, for psbt_flow.py: N P2WPKH inputs with small previous
transactions, ones whose previous transactions are sized as wallets and exchanges make them, P2PKH and a P2SH-P2WSH
2-of-3. CPython, embit.

    .venv/bin/python pico/tests/psbt_cases.py OUT.json
"""
import base64, json, random, sys
from embit import bip32, bip39, script
from embit.psbt import PSBT, DerivationPath
from embit.script import Witness
from embit.transaction import Transaction, TransactionInput, TransactionOutput

H = 0x80000000
root = bip32.HDKey.from_seed(bip39.mnemonic_to_seed("abandon " * 11 + "about"))
# P2SH-P2WSH 2-of-3 cosigners: BIP39's "zoo ... wrong" and "legal winner ... yellow"
COSIGNERS = [bip32.HDKey.from_seed(bip39.mnemonic_to_seed(m)) for m in
             ("zoo " * 11 + "wrong", "legal winner thank year wave sausage worth useful legal winner thank yellow")]
FP = root.my_fingerprint
rng = random.Random(7)
rnd = lambda n: bytes(rng.getrandbits(8) for _ in range(n))


def other_spk():
    k = rng.random()
    if k < 0.45:
        return script.Script(b"\x00\x14" + rnd(20))
    if k < 0.70:
        return script.Script(b"\x51\x20" + rnd(32))
    if k < 0.90:
        return script.Script(b"\xa9\x14" + rnd(20) + b"\x87")
    return script.Script(b"\x76\xa9\x14" + rnd(20) + b"\x88\xac")


def prevtx(spk, value, nin, nout):
    vin = [TransactionInput(rnd(32), rng.randrange(4), sequence=0xFFFFFFFD, witness=Witness([rnd(72), b"\x02" + rnd(32)]))
           for _ in range(nin)]
    vout = [TransactionOutput(rng.randrange(10_000, 5_000_000), other_spk()) for _ in range(nout - 1)]
    at = rng.randrange(nout)
    vout.insert(at, TransactionOutput(value, spk))
    return Transaction(version=2, vin=vin, vout=vout), at


PURPOSE = {"wpkh": [84 | H, H, H], "tr": [86 | H, H, H], "pkh": [44 | H, H, H], "shwsh": [48 | H, H, H, 1 | H]}


def wsh_script(path):
    keys = [root.derive(path).key.get_public_key()] + [c.derive(path).key.get_public_key() for c in COSIGNERS]
    return script.multisig(2, sorted(keys, key=lambda k: k.sec()))


def build(kinds, change=True):
    """kinds: per input ("wpkh" or "pkh", previous tx inputs, previous tx outputs), ("tr",) or ("shwsh",)."""
    vin, meta, total = [], [], 0
    for i, k in enumerate(kinds):
        path = PURPOSE[k[0]] + [0, i]
        key = root.derive(path).key.get_public_key()
        value = 100_000 + i
        spk = {"tr": lambda: script.p2tr(key), "pkh": lambda: script.p2pkh(key),
               "shwsh": lambda: script.p2sh(script.p2wsh(wsh_script(path)))}.get(k[0], lambda: script.p2wpkh(key))()
        ptx, at = prevtx(spk, value, *(k[1:] or (1, 2)))
        vin.append(TransactionInput(ptx.txid(), at, sequence=0xFFFFFFFD))
        meta.append((k, ptx, at, key, path))
        total += value
    ch_path = [84 | H, H, H, 1, 3]
    ch = root.derive(ch_path).key.get_public_key()
    fee = 200 * len(kinds) + 500
    send = (total - fee) // 2
    vout = [TransactionOutput(send, script.Script(b"\x00\x14" + rnd(20)))]
    vout.append(TransactionOutput(total - fee - send, script.p2wpkh(ch) if change else script.Script(b"\x00\x14" + rnd(20))))
    p = PSBT(Transaction(version=2, vin=vin, vout=vout))
    for inp, (k, ptx, at, key, path) in zip(p.inputs, meta):
        if k[0] != "pkh":  # a legacy input has its previous transaction alone
            inp.witness_utxo = ptx.vout[at]
        if k[0] == "tr":
            inp.taproot_bip32_derivations[key] = ([], DerivationPath(FP, path))
            continue
        inp.non_witness_utxo = ptx
        inp.bip32_derivations[key] = DerivationPath(FP, path)
        if k[0] == "shwsh":
            inp.redeem_script, inp.witness_script = script.p2wsh(wsh_script(path)), wsh_script(path)
            for c in COSIGNERS:
                inp.bip32_derivations[c.derive(path).key.get_public_key()] = DerivationPath(c.my_fingerprint, path)
    if change:
        p.outputs[1].bip32_derivations[ch] = DerivationPath(FP, ch_path)
    return p.serialize()


T = lambda: ("wpkh", rng.choice([1, 1, 2]), 2)
CASES = {
    **{f"p2wpkh_{n}in": [("wpkh", 1, 1)] * n for n in (2, 10, 12, 16)},
    "everyday_3in": [T() for _ in range(3)],
    "consol_10in": [T() for _ in range(10)],
    "batch500_2in": [("wpkh", 3, 500), T()],
    "exch_10in_3batch200": [("wpkh", 2, 200) if i in (2, 5, 8) else T() for i in range(10)],
    "taproot_10in": [("tr",)] * 10,
    "mixed_5wpkh_5tr": [T() if i % 2 else ("tr",) for i in range(10)],
    "p2pkh_3in": [("pkh", 1, 2)] * 3,
    "sh_wsh_2of3_2in": [("shwsh",)] * 2,
}
NO_CHANGE = {"sh_wsh_2of3_2in"}  # multisig change would need its descriptor scanned first

if __name__ == "__main__":
    out = {}
    for name, kinds in CASES.items():
        raw = build(kinds, name not in NO_CHANGE)
        out[name] = base64.b64encode(raw).decode()
        print(f"{name:22s} inputs {len(kinds):2d}  {len(raw):6d} B")
    json.dump(out, open(sys.argv[1], "w"), indent=1)
