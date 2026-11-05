from binascii import a2b_base64

import pytest
from embit.descriptor import Descriptor
from embit.psbt import PSBT

from seedsigner.helpers import bitwasm
from seedsigner.helpers.bitwasm import BitwasmError
from seedsigner.models.psbt_parser import (PSBT_IN_TAP_KEY_SIG, PSBTBitwasmDisagreementError,
    PSBTBitwasmRefusedError, PSBTParser)
from seedsigner.models.settings_definition import SettingsConstants

from psbt_testing_util import PSBTTestData, create_output



def build_psbt(psbt_base64: str, *outputs: tuple) -> PSBT:
    """One of the input-only fixtures, with (output hex, amount) outputs."""
    psbt = PSBT.parse(a2b_base64(psbt_base64))
    psbt.outputs.clear()
    for output, amount in outputs:
        psbt.outputs.append(create_output(output, amount))
    return psbt


def embit_signatures(psbt: PSBT, parser: PSBTParser) -> list:
    psbt = PSBT.parse(psbt.serialize())
    psbt.sign_with(parser.root)
    return [dict(inp.partial_sigs) for inp in psbt.inputs]



def test_signs_the_same_ecdsa_signatures_as_embit():
    """RFC6979 nonces on both sides, so the signatures are byte-identical."""
    psbt = PSBT.parse(a2b_base64(PSBTTestData.SINGLE_SIG_NATIVE_SEGWIT_2_INPUTS))
    parser = PSBTParser(p=psbt, seed=PSBTTestData.two_input_seed, network=SettingsConstants.REGTEST)

    assert parser.num_change_outputs == 3
    assert parser.bitwasm_review.display["fee"] == parser.fee_amount == 272

    signed = PSBT.parse(parser.bitwasm_review.sign())
    assert [dict(inp.partial_sigs) for inp in signed.inputs] == embit_signatures(psbt, parser)


def test_signs_taproot():
    psbt = PSBT.parse(a2b_base64(PSBTTestData.SINGLE_SIG_TAPROOT_WITH_CHANGE))
    parser = PSBTParser(p=psbt, seed=PSBTTestData.two_input_seed, network=SettingsConstants.REGTEST)
    assert parser.num_change_outputs == 1

    trimmed = PSBTParser.trim(PSBT.parse(parser.bitwasm_review.sign()))
    assert len(trimmed.inputs[0].unknown[PSBT_IN_TAP_KEY_SIG]) == 64
    assert PSBTParser.sig_count(trimmed) == 1


def test_multisig_change_is_change_once_the_descriptor_registers():
    descriptor = Descriptor.from_string(PSBTTestData.MULTISIG_NATIVE_SEGWIT_DESCRIPTOR)
    change = PSBT.parse(a2b_base64(PSBTTestData.MULTISIG_NATIVE_SEGWIT_1_INPUT)).inputs[0].utxo.value - 100_000 - 500
    psbt = build_psbt(PSBTTestData.MULTISIG_NATIVE_SEGWIT_1_INPUT, (PSBTTestData.SINGLE_SIG_NATIVE_SEGWIT_RECEIVE, 100_000),
                      (PSBTTestData.MULTISIG_NATIVE_SEGWIT_CHANGE, change))

    without = PSBTParser(p=psbt, seed=PSBTTestData.seed, network=SettingsConstants.REGTEST)
    assert not without.bitwasm_review.wallet_registered
    assert without.bitwasm_review.display["spend"] == without.spend_amount + without.change_amount

    parser = PSBTParser(p=psbt, seed=PSBTTestData.seed, network=SettingsConstants.REGTEST, multisig_descriptor=descriptor)
    assert parser.bitwasm_review.wallet_registered
    assert parser.bitwasm_review.display["spend"] == parser.spend_amount == 100_000

    signed = PSBT.parse(parser.bitwasm_review.sign())
    assert [dict(inp.partial_sigs) for inp in signed.inputs] == embit_signatures(psbt, parser)


def test_disagreement_is_refused(monkeypatch):
    psbt = PSBT.parse(a2b_base64(PSBTTestData.SINGLE_SIG_NATIVE_SEGWIT_2_INPUTS))
    real_review = bitwasm.BitwasmReview._review

    def lower_fee(self):
        shown = real_review(self)
        shown["fee"] -= 1
        return shown

    monkeypatch.setattr(bitwasm.BitwasmReview, "_review", lower_fee)
    with pytest.raises(PSBTBitwasmDisagreementError):
        PSBTParser(p=psbt, seed=PSBTTestData.two_input_seed, network=SettingsConstants.REGTEST)


def test_legacy_p2pkh_is_refused():
    psbt = build_psbt(PSBTTestData.SINGLE_SIG_LEGACY_P2PKH_1_INPUT, (PSBTTestData.SINGLE_SIG_NATIVE_SEGWIT_RECEIVE, 100_000))
    with pytest.raises(PSBTBitwasmRefusedError):
        PSBTParser(p=psbt, seed=PSBTTestData.seed, network=SettingsConstants.REGTEST)


def test_sign_refuses_a_psbt_swapped_after_review():
    psbt = PSBT.parse(a2b_base64(PSBTTestData.SINGLE_SIG_NATIVE_SEGWIT_2_INPUTS))
    parser = PSBTParser(p=psbt, seed=PSBTTestData.two_input_seed, network=SettingsConstants.REGTEST)

    psbt.outputs[0].value -= 1_000
    parser.bitwasm_review.psbt_bytes = psbt.serialize()
    with pytest.raises(BitwasmError):
        parser.bitwasm_review.sign()


def test_modules_are_pinned(monkeypatch):
    monkeypatch.setattr(bitwasm, "_parser", None)
    monkeypatch.setattr(bitwasm, "PARSER_SHA256", "00" * 32)
    with pytest.raises(BitwasmError):
        bitwasm._load_parser()
    monkeypatch.setattr(bitwasm, "_signer", None)
    monkeypatch.setattr(bitwasm, "SIGNER_SHA256", "00" * 32)
    with pytest.raises(ValueError):
        bitwasm._load_signer()



@pytest.mark.parametrize("script", [
    b"\x6a", b"\x6a\x04data\x04more", b"\x6a\x4c\x50" + b"B" * 80, b"\x6a\x4d\x0a\x00" + b"E" * 10,
    b"\x6a\x4e\x05\x00\x00\x00hello", b"\x6a\x00\x51\x60\x4f", b"\x6a\x02hi\x51",
    b"\x6a\x10abc", b"\x6a\x4d\x01", b"\x6a\xac", b"\x6a\x02hi\x61",
])
def test_op_return_reads_as_upstream(script):
    """The Pico's OP_RETURN reader agrees with PSBTParser's, which it cannot import, refusals included."""
    from seedsigner.models.psbt_errors import PSBTMalformedOpReturnError
    from seedsigner.models.psbt_wasm import _op_return

    try:
        want = PSBTParser._parse_op_return_payload(script)
    except PSBTMalformedOpReturnError:
        with pytest.raises(PSBTMalformedOpReturnError):
            _op_return(script)
    else:
        assert _op_return(script) == want



@pytest.mark.parametrize("refusal, error", [
    ("review: PREVTX_MISMATCH", "PSBTInputAmountVerificationError"),
    ("review: FEE", "PSBTNegativeFeeError"),
    ("review: NOT_OURS", "PSBTInputOwnershipClaimError"),
    ("review: SIGHASH", "PSBTBitwasmRefusedError"),
])
def test_wasm_refusals_reach_upstreams_errors(monkeypatch, refusal, error):
    """Where upstream has an error of its own, the Pico's parser raises it, so the same screen follows."""
    from seedsigner.models import psbt_errors
    from seedsigner.models.psbt_wasm import WasmPSBTParser

    def refuse(*args, **kwargs):
        raise BitwasmError(refusal)

    monkeypatch.setattr(bitwasm, "BitwasmReview", refuse)
    with pytest.raises(getattr(psbt_errors, error)):
        WasmPSBTParser(b"psbt", seed=object())
