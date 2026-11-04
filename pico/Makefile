# SeedSigner on MicroPython, with bitwasm-signer's signer linked natively (docs/pico.md).
#   make unix BITWASM_SIGNER=<bitwasm-signer checkout>   MicroPython's unix port, for the heap and the tests
BITWASM_SIGNER ?=
MPY_DIR := ../build/micropython
WAMR_ROOT ?= $(BITWASM_SIGNER)/third_party/wasm-micro-runtime
OUT := ../build/pico
BS = $(BITWASM_SIGNER)
SIGNER_SRC = $(addprefix $(BS)/, signer/wasm_main.c signer/core.c signer/address.c signer/bip32.c signer/sighash.c \
  signer/bip39.c signer/seedqr.c signer/bip85.c signer/multisig.c signer/cbor.c signer/ripemd160.c signer/sha512.c \
  signer/secp_callbacks.c signer/secp256k1_unity.c signer/multisig_cbor.c parser/c/src/tx.c parser/c/src/sha256.c)
SIGNER_FLAGS = -Os -DNDEBUG -Wno-unused-function -I$(BS)/signer -I$(BS)/parser/c/include \
  -I$(BS)/third_party/secp256k1/include -I$(BS)/third_party/secp256k1/src -DENABLE_MODULE_EXTRAKEYS=1 \
  -DENABLE_MODULE_SCHNORRSIG=1 -DENABLE_MODULE_RECOVERY=1 -DECMULT_WINDOW_SIZE=2 \
  -DUSE_EXTERNAL_DEFAULT_CALLBACKS=1 -DCOMB_BLOCKS=2 -DCOMB_TEETH=5

$(OUT)/unix/libsigner.a: $(SIGNER_SRC)
	@test -n "$(BITWASM_SIGNER)" || { echo "set BITWASM_SIGNER to a bitwasm-signer checkout at the pinned commit"; exit 1; }
	mkdir -p $(OUT)/unix/obj
	cd $(OUT)/unix/obj && $(CC) $(SIGNER_FLAGS) -c $(abspath $(SIGNER_SRC))
	rm -f $@ && ar rcs $@ $(OUT)/unix/obj/*.o

unix: $(OUT)/unix/libsigner.a
	$(MAKE) -C $(MPY_DIR)/ports/unix -j8 USER_C_MODULES=$(abspath modules) \
	  BITWASM_SIGNER_LIB=$(abspath $(OUT)/unix/libsigner.a) WAMR_ROOT=$(abspath $(WAMR_ROOT)) \
	  WAMR_LIB_DIR=$(abspath ../build/wamr)
.PHONY: unix

# SeedSigner's Python as MicroPython runs it: dataclasses expanded, then pico/lib over the result.
# st7789_mpy.py, the Pi's viper-emitter display driver, is not the Pico's
py:
	rm -rf $(OUT)/py
	python3 tools/to_micropython.py $(OUT)/py ../src/seedsigner ../src/bitwasm_signer
	cp -R lib/. $(OUT)/py/
	cp $(MPY_DIR)/lib/micropython-lib/python-stdlib/logging/logging.py \
	  $(MPY_DIR)/lib/micropython-lib/python-stdlib/hmac/hmac.py $(OUT)/py/
	cp $(MPY_DIR)/lib/micropython-lib/python-stdlib/os-path/os/path.py $(OUT)/py/os/
	rm $(OUT)/py/seedsigner/hardware/displays/st7789_mpy.py
	python3 -c "import sys; print('PARSER = ' + repr(open(sys.argv[1], 'rb').read()))" \
	  ../src/seedsigner/resources/bitwasm/parser.wasm > $(OUT)/py/bitwasm_modules.py
.PHONY: py

# Every module as MicroPython bytecode, which also proves it parses
mpy: py
	rm -rf $(OUT)/mpy
	cd $(OUT)/py && find . -name '*.py' | while read f; do \
	  mkdir -p ../mpy/$$(dirname $$f) && $(abspath $(MPY_DIR))/mpy-cross/build/mpy-cross -o ../mpy/$${f%.py}.mpy $$f || exit 1; done
.PHONY: mpy

# MicroPython for the Pico 2's RISC-V cores with the native signer. PICO_TOOLCHAIN_PATH is a RISC-V GCC,
# such as bitwasm-signer-pico's third_party/riscv-toolchain
rp2: py
	@test -n "$(BITWASM_SIGNER)" || { echo "set BITWASM_SIGNER to a bitwasm-signer checkout at the pinned commit"; exit 1; }
	BITWASM_SIGNER=$(abspath $(BITWASM_SIGNER)) WAMR_ROOT=$(abspath $(WAMR_ROOT)) $(MAKE) -C $(MPY_DIR)/ports/rp2 -j8 BOARD=RPI_PICO2 BOARD_VARIANT=RISCV \
	  USER_C_MODULES=$(abspath modules/micropython.cmake) FROZEN_MANIFEST=$(abspath manifest.py)
.PHONY: rp2

# The one file the device's filesystem needs: everything else is frozen into the firmware
device-install:
	echo "import selftest" > $(OUT)/main.py
	mpremote connect $(PORT) cp $(OUT)/main.py :main.py
.PHONY: device-install

# Run a script on the device with the modules mounted from the host: make device-smoke PORT=/dev/cu.usbmodem...
device-%:
	mpremote connect $(PORT) mount $(OUT)/mpy run tests/$*.py
