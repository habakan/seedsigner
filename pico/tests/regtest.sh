#!/bin/bash
# A regtest spend signed by the Pico: a watch-only wallet for BIP39's abandon...about seed (m/84'/1'/0'),
# a PSBT shown as an animated QR, and the signed one read back from the Pico's screen (drive.py) and mined.
#
#   pico/tests/regtest.sh start | setup | send | grab | broadcast | stop
#
# Needs bitcoind, bitwasm-signer-pico's psbt_host (BIN2UR, for bin2ur and ur2bin) and zbarimg. The Pico runs
# the dev main.py (make device-install-dev) with drive.py serving on build/pico/d.sock, set to Regtest.
set -e
cd "$(dirname "$0")/../.."
R=${REGTEST_DIR:-build/regtest}; PORT=${REGTEST_PORT:-28443}
HOST=${BIN2UR:-../bitwasm-signer-pico/build/host-classic/psbt_host}
cli() { bitcoin-cli -regtest -datadir="$PWD/$R" -rpcport=$PORT "$@"; }
mine() { cli -rpcwallet=miner generatetoaddress "$1" "$(cli -rpcwallet=miner getnewaddress)" >/dev/null; }
case "$1" in
start)
    mkdir -p $R
    # -listen=0: regtest needs no peers, and a sandbox may refuse the P2P port
    bitcoind -regtest -datadir="$PWD/$R" -rpcport=$PORT -listen=0 -daemon -fallbackfee=0.0001 >/dev/null
    for i in $(seq 30); do cli getblockchaininfo >/dev/null 2>&1 && break; sleep 1; done
    ;;
setup)
    tpub=$(.venv/bin/python -c "
from embit import bip39, bip32
from embit.networks import NETWORKS as N
root = bip32.HDKey.from_seed(bip39.mnemonic_to_seed(' '.join(['abandon'] * 11 + ['about'])), version=N['regtest']['xprv'])
print(root.derive('m/84h/1h/0h').to_public().to_base58(version=N['regtest']['xpub']))")
    cli -named createwallet wallet_name=miner >/dev/null
    mine 101
    cli -named createwallet wallet_name=signer disable_private_keys=true blank=true descriptors=true >/dev/null
    for pair in "0:false" "1:true"; do
        d="wpkh([73c5da0a/84h/1h/0h]$tpub/${pair%:*}/*)"
        sum=$(cli getdescriptorinfo "$d" | sed -n 's/.*"checksum": "\([^"]*\)".*/\1/p')
        cli -rpcwallet=signer importdescriptors "[{\"desc\":\"$d#$sum\",\"active\":true,\"internal\":${pair##*:},\"timestamp\":\"now\"}]" >/dev/null
    done
    cli -rpcwallet=miner sendtoaddress "$(cli -rpcwallet=signer getnewaddress "" bech32)" 1.0 >/dev/null
    mine 1
    echo "signer balance: $(cli -rpcwallet=signer getbalance)"
    ;;
send)
    dest=$(cli -rpcwallet=miner getnewaddress "" bech32)
    cli -rpcwallet=signer -named walletcreatefundedpsbt outputs="{\"$dest\":0.1}" fee_rate=2 \
        | sed -n 's/.*"psbt": "\([^"]*\)".*/\1/p' | base64 -d > $R/spend.psbt
    $HOST bin2ur $R/spend.psbt $R/spend
    uv run -q ../tools/psbt/show_ur.py $R/spend.ur $R/spend.gif 400
    echo "show $R/spend.gif to the Pico; 0.1 to $dest"
    ;;
grab)
    # Screenshots of the signed PSBT's animated QR until every pure part has been read (mixed ones help too)
    : > $R/signed.all
    for i in $(seq 80); do
        timeout 30 .venv/bin/python pico/tests/drive.py send build/pico/d.sock "" $R/shot.png >/dev/null 2>&1 || continue
        .venv/bin/python -c "
from PIL import Image
Image.open('$R/shot.png').convert('L').resize((720, 720), Image.NEAREST).save('$R/shot3.png')"
        zbarimg -q --raw $R/shot3.png 2>/dev/null | head -1 >> $R/signed.all || true
        sort -u $R/signed.all | grep '^UR:' > $R/signed.ur || true
        n=$(head -1 $R/signed.ur | sed -E 's|.*/[0-9]+-([0-9]+)/.*|\1|')
        pure=$(awk -F/ -v n="$n" '{split($2,a,"-"); if (a[1]+0 <= n+0) print a[1]}' $R/signed.ur | sort -un | wc -l)
        [ -n "$n" ] && [ "$(wc -l < $R/signed.ur)" -ge $((n * 3)) ] && break
        [ -n "$n" ] && [ "$pure" -ge "$n" ] && break
    done
    echo "$(wc -l < $R/signed.ur) parts of ${n:-?}"
    ;;
broadcast)
    $HOST ur2bin $R/signed.ur $R/signed.psbt
    raw=$(cli finalizepsbt "$(base64 < $R/signed.psbt | tr -d '\n')" | sed -n 's/.*"hex": "\([^"]*\)".*/\1/p')
    [ -n "$raw" ] || { echo "not finalizable: the signature is missing or wrong"; exit 1; }
    cli testmempoolaccept "[\"$raw\"]" | grep '"allowed"'
    txid=$(cli sendrawtransaction "$raw")
    mine 1
    echo "txid $txid"
    cli -rpcwallet=signer gettransaction "$txid" | grep -E '"confirmations"|"blockheight"'
    ;;
stop)
    cli stop
    ;;
esac
