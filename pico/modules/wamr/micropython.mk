# WAMR for the unix port: the software-bounds-checked libiwasm from tools/pico/libiwasm.sh
WAMR_MOD_DIR := $(USERMOD_DIR)
SRC_USERMOD_C += $(WAMR_MOD_DIR)/modwamr.c
CFLAGS_USERMOD += -I$(WAMR_ROOT)/core/iwasm/include
LDFLAGS_USERMOD += -L$(WAMR_LIB_DIR) -liwasm -Wl,-rpath,$(WAMR_LIB_DIR)
