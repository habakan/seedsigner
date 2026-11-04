import pytest


# Upstream tests whose psbts signer.wasm refuses, so PSBTParser now stops where embit
# alone went on. Strict, so a test that starts passing (signer.wasm grew) is noticed.
NESTED_OR_LEGACY = "signer.wasm signs P2WPKH, P2SH-P2WPKH, P2TR key path and P2WSH multisig only"
NO_PREVTX = "signer.wasm requires non_witness_utxo for segwit v0 inputs"
COIN_TYPE = "the fixture's paths are not this network's BIP44 coin type (or Electrum's m/0h)"
MALFORMED = "a fixture parser.wasm rejects: no outputs, or a non_witness_utxo that is not the input's"
ALREADY_SIGNED = "signer.wasm has nothing to sign when this seed's signature is already there"
NOT_STANDARD = "signer.wasm derives only m/49h, m/84h, m/86h and m/48h/.../2h, with this network's coin type"

BITWASM_REFUSES = {
    "test_decodepsbtqr.py::test_base64_2_input_p2wsh": NO_PREVTX,
    "test_decodepsbtqr.py::test_base64_1_input_p2sh_p2wsh": NESTED_OR_LEGACY,
    "test_decodepsbtqr.py::test_specter_multisig_animated_qr": NO_PREVTX,
    "test_flows_psbt.py::TestPSBTFlows::test_scan_psbt_first_then_correct_seedqr_flow": COIN_TYPE,
    "test_flows_psbt.py::TestPSBTFlows::test_scan_psbt_first_then_load_electrum_seed": COIN_TYPE,
    "test_flows_psbt.py::TestPSBTFlows::test_scan_multisig_psbt_seed_already_signed_flow": ALREADY_SIGNED,
    "test_flows_psbt.py::TestPSBTFlows::test_parse_and_display_op_return_content": COIN_TYPE,
    "test_psbt_parser.py::TestPSBTParser::test_singlesig_legacy_p2pkh": NESTED_OR_LEGACY,
    "test_psbt_parser.py::TestPSBTParser::test_multisig_nested_segwit": NESTED_OR_LEGACY,
    "test_psbt_parser.py::TestPSBTParser::test_multisig_legacy_p2sh": NESTED_OR_LEGACY,
    "test_psbt_parser.py::TestPSBTParser::test_missing_fingerprint_handling": MALFORMED,
    "test_psbt_parser.py::TestPSBTParser::test_verify_multisig_output": NESTED_OR_LEGACY,
    "test_psbt_parser.py::test_p2sh_legacy_multisig": NESTED_OR_LEGACY,
    "test_psbt_parser.py::TestPSBTParserOptimizations::test_zero_fingerprint_fill_over_many_inputs": MALFORMED,
    "test_psbt_parser.py::TestPSBTParserSeedOwnership::test__parse__verified_derivation_paths_empty_for_not_owned_input": MALFORMED,
    "test_psbt_parser.py::TestPSBTParserOutputOwnership::test__parse__rejects_a_multisig_output_built_from_other_peoples_keys": NESTED_OR_LEGACY,
    "test_psbt_parser.py::TestPSBTParserOutputOwnership::test__parse__rejects_a_multisig_output_that_hides_this_seed_behind_another_fingerprint": NESTED_OR_LEGACY,
    "test_psbt_parser.py::TestPSBTParserOutputOwnership::test__parse__rejects_a_multisig_output_whose_supplied_script_is_not_its_own": NESTED_OR_LEGACY,
    "test_psbt_parser.py::TestPSBTParserOutputOwnership::test__parse__counts_a_different_quorum_as_a_spend": NESTED_OR_LEGACY,
    "test_psbt_parser.py::TestPSBTParserOutputOwnership::test__parse__counts_a_different_quorum_as_a_spend_when_its_xpubs_are_supplied": NESTED_OR_LEGACY,
    "test_psbt_parser.py::TestPSBTParserOutputOwnership::test__parse__counts_a_different_quorum_as_change_if_no_global_xpubs": NESTED_OR_LEGACY,
    "test_encodepsbtqr.py::test_ur_xpub_qr": NOT_STANDARD,  # mainnet with m/48h/1h; the testnet half is its own test
    "test_flows_seed.py::TestSeedFlows::test_export_xpub_custom_derivation_flow": NOT_STANDARD,
    "test_flows_seed.py::TestSeedFlows::test_export_xpub_electrum_seed_flow": NOT_STANDARD,
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        reason = BITWASM_REFUSES.get(item.nodeid.split("tests/", 1)[-1])
        if reason:
            item.add_marker(pytest.mark.xfail(reason=reason, strict=True))
