import pytest


# Upstream tests whose psbts signer.wasm refuses, so PSBTParser now stops where embit
# alone went on. Strict, so a test that starts passing (signer.wasm grew) is noticed.
MALFORMED = "a fixture parser.wasm rejects: no outputs, or a non_witness_utxo that is not the input's"
ALREADY_SIGNED = "signer.wasm has nothing to sign when this seed's signature is already there"
SPK_MAX = "parser.wasm takes output scripts of at most 83 bytes, so an OP_RETURN of at most 80"

BITWASM_REFUSES = {
    "test_flows_psbt.py::TestPSBTFlows::test_scan_multisig_psbt_seed_already_signed_flow": ALREADY_SIGNED,
    "test_psbt_parser.py::TestPSBTParser::test_missing_fingerprint_handling": MALFORMED,
    "test_psbt_parser.py::TestPSBTParserOptimizations::test_zero_fingerprint_fill_over_many_inputs": MALFORMED,
    "test_psbt_parser.py::test_parse_op_return_content_pushdata2": SPK_MAX,
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        node = item.nodeid.split("tests/", 1)[-1]
        reason = BITWASM_REFUSES.get(node)
        if reason:
            item.add_marker(pytest.mark.xfail(reason=reason, strict=True))


# Every successful embit PSBTParser.parse in the suite is repeated with WasmPSBTParser, the Pico's,
# and the answers the views read must agree, P2WSH change claimed before any descriptor included
WASM_PARSER_CHECKS = {"compared": 0, "unproven": 0}


@pytest.fixture(autouse=True)
def compare_with_wasm_parser(monkeypatch, request):
    if "screenshot_generator" in str(request.node.fspath):
        return  # screenshots, not a check; their PSBTs use testnet paths on mainnet
    from seedsigner.models.psbt_parser import PSBTParser
    from seedsigner.models.psbt_wasm import WasmPSBTParser
    parse = PSBTParser.parse

    def checked(self):
        ok = parse(self)
        if ok:
            w = WasmPSBTParser(self.psbt, self.seed, self.network, self.psbt_bytes, self.multisig_descriptor)
            fields = ["fee_amount", "verified_input_amount", "num_inputs", "op_return_data", "is_multisig", "spend_amount",
                      "change_amount", "destination_addresses", "destination_amounts", "is_high_fee"]
            want = [(c["output_index"], c["address"], c["amount"], list(c["verified_derivation_path"])) for c in self.change_data]
            got = [(c["output_index"], c["address"], c["amount"], c["verified_derivation_path"]) for c in w.change_data]
            if got != want and w.bitwasm_review.unverified_change:
                # A claim upstream drops for its missing witness script, which the plan cannot show: not signed unproven
                fields = fields[:5]
                WASM_PARSER_CHECKS["unproven"] += 1
            else:
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
                                f"({WASM_PARSER_CHECKS['unproven']} with change claimed that only a descriptor can prove)")


# SEEDSIGNER_RECORD_QR=<file>: every DecodeQR session in the suite (its add_data calls) is written there,
# for pico/tests/qr_replay.py to decode again on MicroPython and compare with CPython
QR_SESSIONS = []


@pytest.fixture(autouse=True)
def record_qr_sessions(monkeypatch):
    import os
    if not os.environ.get("SEEDSIGNER_RECORD_QR"):
        return
    from binascii import b2a_base64
    from seedsigner.models.decode_qr import DecodeQR
    add_data = DecodeQR.add_data

    def recorded(self, data):
        if not hasattr(self, "_recorded"):
            self._recorded = {"lang": self.wordlist_language_code, "data": []}
            QR_SESSIONS.append(self._recorded)
        if data is not None:
            raw = bytes(data) if isinstance(data, (bytes, bytearray)) else None
            self._recorded["data"].append(["b", b2a_base64(raw).decode().strip()] if raw is not None else ["s", data])
        return add_data(self, data)

    monkeypatch.setattr(DecodeQR, "add_data", recorded)


def pytest_sessionfinish(session):
    import json, os
    path = os.environ.get("SEEDSIGNER_RECORD_QR")
    if path:
        unique = {json.dumps(s, sort_keys=True) for s in QR_SESSIONS if s["data"]}
        with open(path, "w") as f:  # one session a line, so the Pico can read them one at a time
            f.write("".join(s + "\n" for s in sorted(unique)))
