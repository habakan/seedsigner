"""bitwasm_signer.wamr on MicroPython, as the browser simulator swaps in the browser's WebAssembly.
Instance(None) is the signer linked into the firmware; Instance(wasm) runs a module on _wamr."""
import _bitwasm
import _wamr


class Instance:
    def __init__(self, wasm, lib_path=None):
        if wasm is None:
            self._e = _bitwasm
            self.memory = _bitwasm.memory()
        else:
            self._e = _wamr.Instance(wasm)
            self.memory = self._e.memory()

    def __getattr__(self, name):
        if self._e is _bitwasm:
            return getattr(_bitwasm, name)
        call = self._e.call
        return lambda *args: call(name, *args)
