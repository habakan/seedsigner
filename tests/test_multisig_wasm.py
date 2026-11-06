"""The Pico's multisig, without embit: wallet.Multisig and WasmPSBTParser's change, against embit's answers."""
from binascii import a2b_base64

import pytest
from embit.descriptor import Descriptor
from embit.psbt import PSBT

from seedsigner.helpers import bitwasm, embit_utils, wallet
from seedsigner.helpers.bitwasm import BitwasmError
from seedsigner.models.psbt_wasm import WasmPSBTParser
from seedsigner.models.seed import Seed
from seedsigner.models.settings_definition import SettingsConstants

from psbt_testing_util import PSBTTestData
from test_bitwasm import build_psbt

DESC = PSBTTestData.MULTISIG_NATIVE_SEGWIT_DESCRIPTOR
NET = SettingsConstants.REGTEST


def registered(descriptor=DESC):
    m = wallet.Multisig(descriptor)
    assert m.register([PSBTTestData.seed], NET)
    return m


def test_children_as_the_signer_reads_them():
    k = "[0fb882ff/48h/1h/0h/2h]tpubX"
    assert wallet._multipath(f"wsh(sortedmulti(2,{k}/{{0,1}}/*,{k}))#abcd1234") == \
        f"wsh(sortedmulti(2,{k}/<0;1>/*,{k}/<0;1>/*))"
    assert wallet._multipath(f"wsh(sortedmulti(1,{k}/0/*))") == f"wsh(sortedmulti(1,{k}/<0;1>/*))"
    assert wallet._multipath(f"wsh(sortedmulti(1,{k}/<0;1>/*))#abcd1234") == f"wsh(sortedmulti(1,{k}/<0;1>/*))#abcd1234"


def test_policy_and_addresses_as_embit():
    m = registered()
    d = Descriptor.from_string(DESC)
    assert wallet.multisig_policy(m) == wallet.multisig_policy(d)
    for change in (False, True):
        for i in range(3):
            want = embit_utils.get_multisig_address(d, index=i, is_change=change, embit_network="regtest")
            assert wallet.multisig_address(m, i, change, NET) == want


def test_watched_without_a_seed_of_ours():
    d = Descriptor.from_string(DESC)
    for seeds in ([], [Seed(("abandon " * 11 + "about").split())]):
        m = wallet.Multisig(DESC)
        assert m.register(seeds, NET) and m.seed is None and m.info["ours"] == 255
        assert wallet.multisig_policy(m) == wallet.multisig_policy(d)
        assert wallet.multisig_address(m, 2, True, NET) == embit_utils.get_multisig_address(
            d, index=2, is_change=True, embit_network="regtest")


def test_an_unreadable_descriptor_does_not_register():
    assert not wallet.Multisig("wsh(pk(nothing))").register([PSBTTestData.seed], NET)


def change_psbt():
    change = PSBT.parse(a2b_base64(PSBTTestData.MULTISIG_NATIVE_SEGWIT_1_INPUT)).inputs[0].utxo.value - 100_000 - 500
    return build_psbt(PSBTTestData.MULTISIG_NATIVE_SEGWIT_1_INPUT, (PSBTTestData.SINGLE_SIG_NATIVE_SEGWIT_RECEIVE, 100_000),
                      (PSBTTestData.MULTISIG_NATIVE_SEGWIT_CHANGE, change)).serialize()


def test_claimed_change_is_signed_only_once_a_descriptor_proves_it():
    p = WasmPSBTParser(change_psbt(), PSBTTestData.seed, NET)
    assert p.is_multisig and p.num_change_outputs == 1 and p.spend_amount == 100_000
    with pytest.raises(BitwasmError):
        p.bitwasm_review.sign()

    assert p.verify_multisig_output(registered(), change_num=0)
    assert p.bitwasm_review.wallet_registered and p.bitwasm_review.sign()


def test_another_wallet_does_not_prove_the_change():
    p = WasmPSBTParser(change_psbt(), PSBTTestData.seed, NET)
    other = DESC.replace("sortedmulti(2,", "sortedmulti(1,").split("#")[0]
    assert not p.verify_multisig_output(registered(other), change_num=0)
