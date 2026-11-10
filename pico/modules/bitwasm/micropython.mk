# The native signer for the unix port, as a library built with bitwasm-signer's own flags
# (MicroPython's -Werror would reject secp256k1's unused functions): see pico/Makefile
BITWASM_MOD_DIR := $(USERMOD_DIR)
SRC_USERMOD_C += $(BITWASM_MOD_DIR)/modbitwasm.c
LDFLAGS_USERMOD += $(BITWASM_SIGNER_LIB)
# plan.h, and prevtx_buf's size from wasm_main.c, as micropython.cmake has them for the rp2 port
CFLAGS_USERMOD += -I$(BITWASM_SIGNER)/parser/c/include -DBITWASM_PREVTX_MAX=$(shell sed -n 's/^\#define PREVTX_MAX \([0-9]*\)$$/\1/p' $(BITWASM_SIGNER)/signer/wasm_main.c)
