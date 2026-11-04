"""bitwasm_signer.wamr on MicroPython. Instance(None) is the signer linked into the firmware, as the
browser simulator swaps in the browser's WebAssembly; parser.wasm on WAMR is not here yet."""
import _bitwasm


class Instance:
    def __init__(self, wasm, lib_path=None):
        if wasm is not None:
            raise NotImplementedError("parser.wasm on WAMR is not in this firmware yet")
        self.memory = _bitwasm.memory()

    def __getattr__(self, name):
        return getattr(_bitwasm, name)
