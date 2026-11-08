"""
PSBTs for BIP39's test seed (abandon x11 about), mainnet, for psbt_flow.py: N P2WPKH inputs with small previous
transactions, and ones whose previous transactions are sized as wallets and exchanges make them. CPython, embit.

    .venv/bin/python pico/tests/psbt_cases.py OUT.json
"""
import base64, json, random, sys
from embit import bip32, bip39, script
from embit.psbt import PSBT, DerivationPath
from embit.script import Witness
from embit.transaction import Transaction, TransactionInput, TransactionOutput

H = 0x80000000
root = bip32.HDKey.from_seed(bip39.mnemonic_to_seed("abandon " * 11 + "about"))
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


def build(kinds):
    """kinds: per input ("wpkh", previous tx inputs, previous tx outputs) or ("tr",)."""
    vin, meta, total = [], [], 0
    for i, k in enumerate(kinds):
        path = [(86 if k[0] == "tr" else 84) | H, H, H, 0, i]
        key = root.derive(path).key.get_public_key()
        value = 100_000 + i
        ptx, at = prevtx(script.p2tr(key) if k[0] == "tr" else script.p2wpkh(key), value, *(k[1:] or (1, 2)))
        vin.append(TransactionInput(ptx.txid(), at, sequence=0xFFFFFFFD))
        meta.append((k, ptx, at, key, path))
        total += value
    ch_path = [84 | H, H, H, 1, 3]
    ch = root.derive(ch_path).key.get_public_key()
    fee = 200 * len(kinds) + 500
    send = (total - fee) // 2
    p = PSBT(Transaction(version=2, vin=vin, vout=[TransactionOutput(send, script.Script(b"\x00\x14" + rnd(20))),
                                                    TransactionOutput(total - fee - send, script.p2wpkh(ch))]))
    for inp, (k, ptx, at, key, path) in zip(p.inputs, meta):
        inp.witness_utxo = ptx.vout[at]
        if k[0] == "tr":
            inp.taproot_bip32_derivations[key] = ([], DerivationPath(FP, path))
        else:
            inp.non_witness_utxo = ptx
            inp.bip32_derivations[key] = DerivationPath(FP, path)
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
}

if __name__ == "__main__":
    out = {}
    for name, kinds in CASES.items():
        raw = build(kinds)
        out[name] = base64.b64encode(raw).decode()
        print(f"{name:22s} inputs {len(kinds):2d}  {len(raw):6d} B")
    json.dump(out, open(sys.argv[1], "w"), indent=1)
