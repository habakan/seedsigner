import pytest


# Upstream tests whose psbts signer.wasm refuses, so PSBTParser now stops where embit
# alone went on. Strict, so a test that starts passing (signer.wasm grew) is noticed.
NESTED_OR_LEGACY = "signer.wasm signs P2WPKH, P2SH-P2WPKH, P2TR key path and P2WSH multisig only"
NO_PREVTX = "signer.wasm requires non_witness_utxo for segwit v0 inputs"
COIN_TYPE = "the fixture's paths are not this network's BIP44 coin type (or Electrum's m/0h)"
MALFORMED = "a fixture parser.wasm rejects: no outputs, or a non_witness_utxo that is not the input's"
ALREADY_SIGNED = "signer.wasm has nothing to sign when this seed's signature is already there"
MESSAGE_MAX = "signer.wasm signs messages of at most 512 bytes; the multipage scenario's is 576"
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
    "test_flows_seed.py::TestMessageSigningFlows::test_sign_message_flow": MESSAGE_MAX,
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        reason = BITWASM_REFUSES.get(item.nodeid.split("tests/", 1)[-1])
        if reason:
            item.add_marker(pytest.mark.xfail(reason=reason, strict=True))


# Every successful embit PSBTParser.parse in the suite is repeated with WasmPSBTParser, the Pico's,
# and the answers the views read must agree. The one allowed difference is P2WSH change without a
# registered descriptor, which the signer calls external; then the change fields are not compared
WASM_PARSER_CHECKS = {"compared": 0, "change_skipped": 0}


@pytest.fixture(autouse=True)
def compare_with_wasm_parser(monkeypatch):
    from seedsigner.models.psbt_parser import PSBTParser
    from seedsigner.models.psbt_wasm import WasmPSBTParser
    parse = PSBTParser.parse

    def checked(self):
        ok = parse(self)
        if ok:
            w = WasmPSBTParser(self.psbt, self.seed, self.network, self.psbt_bytes, self.multisig_descriptor)
            fields = ["fee_amount", "input_amount", "num_inputs", "op_return_data", "is_multisig"]
            if self.is_multisig and not w.bitwasm_review.wallet_registered:
                WASM_PARSER_CHECKS["change_skipped"] += 1
            else:
                fields += ["spend_amount", "change_amount", "destination_addresses", "destination_amounts", "is_high_fee"]
                want = [(c["output_index"], c["address"], c["amount"], list(c["verified_derivation_path"])) for c in self.change_data]
                got = [(c["output_index"], c["address"], c["amount"], c["verified_derivation_path"]) for c in w.change_data]
                assert got == want, f"change_data: wasm {got}, embit {want}"
            for f in fields:
                assert getattr(w, f) == getattr(self, f), f"{f}: wasm {getattr(w, f)!r}, embit {getattr(self, f)!r}"
            assert (w.policy or {}).get("type") == (self.policy or {}).get("type")
            assert (w.policy or {}).get("m") == (self.policy or {}).get("m")
            WASM_PARSER_CHECKS["compared"] += 1
        return ok

    monkeypatch.setattr(PSBTParser, "parse", checked)


def pytest_terminal_summary(terminalreporter):
    terminalreporter.write_line(f"WasmPSBTParser agreed with PSBTParser on {WASM_PARSER_CHECKS['compared']} parses "
                                f"({WASM_PARSER_CHECKS['change_skipped']} without comparing unregistered multisig change)")
