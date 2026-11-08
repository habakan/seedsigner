"""
Regtest spends signed by the device, as psbt_flow.py drives it, set to Regtest: Bitcoin Core's watch-only wallet for
BIP39's test seed (coin type 1) funds P2WPKH beside P2TR, P2PKH, and a 2-of-3 P2SH-P2WSH whose cosigner is a Core
wallet holding the "zoo ... wrong" seed. The signed PSBT is read off the screen's animated QR, combined with the
unsigned one, finalized, broadcast and mined.

    .venv/bin/python pico/tests/regtest.py PORT [--reset CMD]

Needs bitcoind and zbar (DYLD_LIBRARY_PATH=/opt/homebrew/lib on macOS). The node runs in build/pico/regtest, started
afresh and stopped at the end.
"""
import argparse, base64, json, shutil, subprocess, time
from embit import bip32, bip39
from embit.networks import NETWORKS
import psbt_flow as F

D, PORT = F.R / "build/pico/regtest", "28443"
T = NETWORKS["test"]


def cli(*a):
    return subprocess.run(["bitcoin-cli", "-regtest", f"-datadir={D}", f"-rpcport={PORT}", *a],
                          capture_output=True, text=True, check=True).stdout.strip()


def hd(words):
    return bip32.HDKey.from_seed(bip39.mnemonic_to_seed(words), version=T["xprv"])


ME, COS = hd("abandon " * 11 + "about"), [hd("zoo " * 11 + "wrong"),
                                         hd("legal winner thank year wave sausage worth useful legal winner thank yellow")]


def key(k, path, chain, priv=False):
    x = k.derive(path)
    return f"[{k.my_fingerprint.hex()}{path[1:]}]" + (x.to_base58(T["xprv"]) if priv else x.to_public().to_base58(T["xpub"])) + f"/{chain}/*"


def desc(d):
    return d + "#" + json.loads(cli("getdescriptorinfo", d))["checksum"]  # Core's own form would drop a tprv


def multi(chain, priv=None):
    return desc(f"sh(wsh(sortedmulti(2,{','.join(key(k, 'm/48h/1h/0h/1h', chain, k is priv) for k in [ME] + COS)})))")


def setup():
    shutil.rmtree(D, ignore_errors=True); D.mkdir(parents=True)
    # -listen=0: regtest needs no peers, and a sandbox may refuse the P2P port
    subprocess.run(["bitcoind", "-regtest", f"-datadir={D}", f"-rpcport={PORT}", "-listen=0", "-daemon", "-fallbackfee=0.0001"], check=True)
    for _ in range(30):
        try:
            cli("getblockchaininfo"); break
        except subprocess.CalledProcessError:
            time.sleep(1)
    cli("createwallet", "miner")
    cli("-named", "createwallet", "wallet_name=dev", "disable_private_keys=true", "blank=true")
    single = [desc(f"{w}({key(ME, p, c)})") for c in (0, 1) for w, p in [("wpkh", "m/84h/1h/0h"), ("pkh", "m/44h/1h/0h"), ("tr", "m/86h/1h/0h")]]
    imported("dev", [{"desc": d, "timestamp": "now", "active": True, "internal": "/1/*" in d} for d in single] +
             [{"desc": multi(c), "timestamp": "now", "internal": c == 1} for c in (0, 1)])
    cli("-named", "createwallet", "wallet_name=cos", "blank=true")
    imported("cos", [{"desc": multi(c, COS[0]), "timestamp": "now"} for c in (0, 1)])
    mine(101)
    to = [cli("-rpcwallet=dev", "getnewaddress", "", t) for t in ("bech32", "bech32", "bech32m", "legacy", "legacy")]
    for a in to + json.loads(cli("deriveaddresses", multi(0), "[0,1]")):
        cli("-rpcwallet=miner", "sendtoaddress", a, "0.5")
    mine(1)


def imported(wallet, reqs):
    if not all(r["success"] for r in json.loads(cli(f"-rpcwallet={wallet}", "importdescriptors", json.dumps(reqs)))):
        raise SystemExit(f"{wallet}: a descriptor was refused")


def mine(n):
    cli("generatetoaddress", str(n), cli("-rpcwallet=miner", "getnewaddress"))


def psbts():
    utxos = json.loads(cli("-rpcwallet=dev", "listunspent"))
    kind = lambda u: "shwsh" if u["desc"].startswith("sh(wsh") else u["desc"].split("(")[0]

    def make(kinds, amount, change):
        ins = [{"txid": u["txid"], "vout": u["vout"]} for u in utxos if kind(u) in kinds]
        opts = {"add_inputs": False, **({"change_type": change} if change else {"subtractFeeFromOutputs": [0]})}
        out = json.dumps([{cli("-rpcwallet=miner", "getnewaddress"): amount}])
        return json.loads(cli("-rpcwallet=dev", "walletcreatefundedpsbt", json.dumps(ins), out, "0", json.dumps(opts), "true"))["psbt"]
    return {"wpkh_tr": make(("wpkh", "tr"), 0.7, "bech32"), "pkh": make(("pkh",), 0.6, "legacy"),
            "sh_wsh_2of3": make(("shwsh",), 1.0, None)}


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("port"); a.add_argument("--reset")
    args = a.parse_args()
    F.OUT.mkdir(parents=True, exist_ok=True)
    setup()
    try:
        for name, unsigned in psbts().items():
            print(name)
            signed = F.run(args.port, f"regtest_{name}", base64.b64decode(unsigned), args.reset, network="R", from_screen=True)
            if signed is None:
                print("  no signed QR read"); continue
            parts = [unsigned, base64.b64encode(signed).decode()]
            if name.startswith("sh_wsh"):
                parts.append(json.loads(cli("-rpcwallet=cos", "walletprocesspsbt", unsigned))["psbt"])
            fin = json.loads(cli("finalizepsbt", cli("combinepsbt", json.dumps(parts))))
            if not fin["complete"]:
                print("  not finalizable: a signature is missing or wrong"); continue
            txid = cli("sendrawtransaction", fin["hex"])
            mine(1)
            print(f"  signed {len(signed)} B, mined {txid}")
    finally:
        cli("stop")
