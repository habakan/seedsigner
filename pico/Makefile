# SeedSigner on MicroPython, with bitwasm-signer's signer linked natively (docs/pico.md).
#   make unix BITWASM_SIGNER=<bitwasm-signer checkout>   MicroPython's unix port, for the heap and the tests
BITWASM_SIGNER ?=
MPY_DIR := ../build/micropython
# urtypes as requirements.txt pins it, from the venv the tests use
URTYPES ?= $(shell ../.venv/bin/python -c "import os, urtypes; print(os.path.dirname(urtypes.__file__))")
WAMR_ROOT ?= $(BITWASM_SIGNER)/third_party/wasm-micro-runtime
OUT := ../build/pico
# UI languages frozen in besides English: by default those OpenSans covers. A CJK language brings a Noto font
# of 0.6 to 0.7 MB, so it goes in on its own: make rp2 LOCALES=ja (or ko, zh_Hans_CN)
LOCALES ?= ca cs de el es fr id it nl no pl pt_BR ru tr vi
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
	  BITWASM_SIGNER=$(abspath $(BS)) BITWASM_SIGNER_LIB=$(abspath $(OUT)/unix/libsigner.a) WAMR_ROOT=$(abspath $(WAMR_ROOT)) \
	  WAMR_LIB_DIR=$(abspath ../build/wamr)
.PHONY: unix

# SeedSigner's Python as MicroPython runs it: dataclasses expanded, then pico/lib and micropython-pil's PIL
# over the result. st7789_mpy.py, the Pi's viper-emitter display driver, is not the Pico's
PIL_DIR = third_party/micropython-pil
py:
	@test -f $(PIL_DIR)/PIL/Image.py || { echo "git submodule update --init pico/third_party/micropython-pil"; exit 1; }
	rm -rf $(OUT)/py
	python3 tools/to_micropython.py $(OUT)/py ../src/seedsigner ../src/bitwasm_signer $(URTYPES)
	cp -R lib/. $(OUT)/py/
	cp -R $(PIL_DIR)/PIL $(OUT)/py/ && rm -rf $(OUT)/py/PIL/_gfx_sim.py $(OUT)/py/PIL/__pycache__
	cp $(MPY_DIR)/lib/micropython-lib/python-stdlib/hmac/hmac.py \
	  $(MPY_DIR)/lib/micropython-lib/python-stdlib/base64/base64.py \
	  $(MPY_DIR)/lib/micropython-lib/python-stdlib/zlib/zlib.py \
	  $(MPY_DIR)/lib/micropython-lib/python-stdlib/datetime/datetime.py $(OUT)/py/
	cp $(MPY_DIR)/lib/micropython-lib/python-stdlib/os-path/os/path.py $(OUT)/py/os/
	rm $(OUT)/py/seedsigner/hardware/displays/st7789_mpy.py
	../.venv/bin/python tools/make_fonts.py $(OUT)/py/pil_fonts ../src/seedsigner/resources/fonts fonts_used.json $(LOCALES)
	../.venv/bin/python $(PIL_DIR)/tools/make_images.py $(OUT)/py/pil_images ../src/seedsigner/resources/img > /dev/null
	../.venv/bin/python tools/make_l10n.py $(OUT)/py/pico_l10n ../src/seedsigner/resources/seedsigner-translations/l10n $(LOCALES) > /dev/null
	printf 'NAME = "%s"\nFORK = "%s"\nSHORT_COMMIT_HASH = "%s"\n' "$$(git describe --tags --exact-match 2>/dev/null || git rev-parse --abbrev-ref HEAD)" \
	  "$$(git remote get-url origin | sed -E 's|.*[:/]([^/]+)/[^/]+$$|\1|')" "$$(git rev-parse --short HEAD)" > $(OUT)/py/pico_version.py
	python3 -c "import sys; print('PARSER = ' + repr(open(sys.argv[1], 'rb').read()))" \
	  ../src/seedsigner/resources/bitwasm/parser-no-ur.wasm > $(OUT)/py/bitwasm_modules.py
.PHONY: py

# Every module as MicroPython bytecode, which also proves it parses
mpy: py
	rm -rf $(OUT)/mpy
	cd $(OUT)/py && find . -name '*.py' | while read f; do \
	  mkdir -p ../mpy/$$(dirname $$f) && $(abspath $(MPY_DIR))/mpy-cross/build/mpy-cross -o ../mpy/$${f%.py}.mpy $$f || exit 1; done
.PHONY: mpy

# MicroPython for the Pico 2's RISC-V cores; PICO_TOOLCHAIN_PATH is a RISC-V GCC. The fonts outgrow 1 MB of
# firmware, so it gets 3 MB and the filesystem 1 MB; passed in the environment so the port's CMAKE_ARGS stay
# MicroPython fixes the firmware needs (patches/), applied once to the checkout
patch:
	@for p in $(abspath patches)/*.patch; do \
	  git -C $(MPY_DIR) apply --reverse --check $$p 2>/dev/null || git -C $(MPY_DIR) apply $$p || exit 1; done
.PHONY: patch

rp2: py patch
	@test -n "$(BITWASM_SIGNER)" || { echo "set BITWASM_SIGNER to a bitwasm-signer checkout at the pinned commit"; exit 1; }
	BITWASM_SIGNER=$(abspath $(BITWASM_SIGNER)) WAMR_ROOT=$(abspath $(WAMR_ROOT)) \
	  CMAKE_ARGS=-DMICROPY_HW_FLASH_STORAGE_BYTES=1048576 $(MAKE) -C $(MPY_DIR)/ports/rp2 -j8 BOARD=RPI_PICO2 BOARD_VARIANT=RISCV \
	  USER_C_MODULES=$(abspath modules/micropython.cmake) FROZEN_MANIFEST=$(abspath manifest.py)
.PHONY: rp2

# The one file the device's filesystem needs: everything else is frozen into the firmware. It starts
# SeedSigner; `import selftest` at the REPL checks the seed and PSBT code instead
device-install:
	printf 'import pico_boot\nfrom seedsigner.controller import Controller\nController.get_instance().start()\n' > $(OUT)/main.py
	mpremote connect $(PORT) cp $(OUT)/main.py :main.py
.PHONY: device-install

# The same with buttons pressed and the screen read over USB serial (pico/lib/RPi/GPIO.py, tests/drive.py):
# for development only, since a signer should take no input but its own buttons and camera
device-install-dev:
	printf 'import pico_boot\nimport RPi.GPIO\nRPi.GPIO.serial_keys = True\nfrom seedsigner.controller import Controller\nController.get_instance().start()\n' > $(OUT)/main.py
	mpremote connect $(PORT) cp $(OUT)/main.py :main.py
.PHONY: device-install-dev

# The device without the device: the unix port with SeedSigner frozen in and micropython-pil's _gfx drawing to no
# display, for pico/tests/sim_main.py (psbt_flow.py sim). Linux only: on macOS the port crashed in SeedSigner's threads
sim: py patch $(OUT)/unix/libsigner.a
	$(MAKE) -C $(MPY_DIR)/ports/unix -j8 BUILD=build-sim MICROPY_PY_THREAD_GIL=1 FROZEN_MANIFEST=$(abspath manifest_sim.py) \
	  USER_C_MODULES="$(abspath modules) $(abspath $(PIL_DIR)/cmod)" BITWASM_SIGNER=$(abspath $(BS)) \
	  BITWASM_SIGNER_LIB=$(abspath $(OUT)/unix/libsigner.a) WAMR_ROOT=$(abspath $(WAMR_ROOT)) WAMR_LIB_DIR=$(abspath ../build/wamr)
.PHONY: sim

# Run a script on the device with the modules mounted from the host: make device-smoke PORT=/dev/cu.usbmodem...
device-%:
	mpremote connect $(PORT) mount $(OUT)/mpy run tests/$*.py
