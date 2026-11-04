"""The PSBT parser the views use: embit's where it is installed, else parser.wasm and the signer's."""
try:
    from seedsigner.models.psbt_parser import PSBTParser
except ImportError:  # the Pico build has no embit
    from seedsigner.models.psbt_wasm import WasmPSBTParser as PSBTParser
