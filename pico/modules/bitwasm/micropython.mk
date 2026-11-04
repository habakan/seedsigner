# The native signer for the unix port, as a library built with bitwasm-signer's own flags
# (MicroPython's -Werror would reject secp256k1's unused functions): see pico/Makefile
BITWASM_MOD_DIR := $(USERMOD_DIR)
SRC_USERMOD_C += $(BITWASM_MOD_DIR)/modbitwasm.c
LDFLAGS_USERMOD += $(BITWASM_SIGNER_LIB)
