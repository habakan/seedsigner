# SeedSigner on MicroPython, with bitwasm-signer's signer linked natively (docs/pico.md).
#   make unix BITWASM_SIGNER=<bitwasm-signer checkout>   MicroPython's unix port, for the heap and the tests
BITWASM_SIGNER ?= $(error set BITWASM_SIGNER to a bitwasm-signer checkout at the pinned commit)
MPY_DIR := ../build/micropython
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
	mkdir -p $(OUT)/unix/obj
	cd $(OUT)/unix/obj && $(CC) $(SIGNER_FLAGS) -c $(abspath $(SIGNER_SRC))
	rm -f $@ && ar rcs $@ $(OUT)/unix/obj/*.o

unix: $(OUT)/unix/libsigner.a
	$(MAKE) -C $(MPY_DIR)/ports/unix -j8 USER_C_MODULES=$(abspath modules) \
	  BITWASM_SIGNER_LIB=$(abspath $(OUT)/unix/libsigner.a)
.PHONY: unix
