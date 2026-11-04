# The native signer for the rp2 port. Its own library, so MicroPython's -Werror and warnings stay off
# bitwasm-signer's C, which builds with its own flags; BITWASM_SIGNER is a checkout at the pinned commit
set(BS $ENV{BITWASM_SIGNER})
if(NOT BS)
  message(FATAL_ERROR "set BITWASM_SIGNER to a bitwasm-signer checkout at the pinned commit")
endif()
add_library(bitwasm_signer STATIC
  ${BS}/signer/wasm_main.c ${BS}/signer/core.c ${BS}/signer/address.c ${BS}/signer/bip32.c ${BS}/signer/sighash.c
  ${BS}/signer/bip39.c ${BS}/signer/seedqr.c ${BS}/signer/bip85.c ${BS}/signer/multisig.c ${BS}/signer/cbor.c
  ${BS}/signer/ripemd160.c ${BS}/signer/sha512.c ${BS}/signer/secp_callbacks.c ${BS}/signer/secp256k1_unity.c
  ${BS}/signer/multisig_cbor.c ${BS}/parser/c/src/tx.c ${BS}/parser/c/src/sha256.c)
target_include_directories(bitwasm_signer PRIVATE ${BS}/signer ${BS}/parser/c/include
  ${BS}/third_party/secp256k1/include ${BS}/third_party/secp256k1/src)
target_compile_definitions(bitwasm_signer PRIVATE NDEBUG ENABLE_MODULE_EXTRAKEYS=1 ENABLE_MODULE_SCHNORRSIG=1
  ENABLE_MODULE_RECOVERY=1 ECMULT_WINDOW_SIZE=2 USE_EXTERNAL_DEFAULT_CALLBACKS=1 COMB_BLOCKS=2 COMB_TEETH=5)
target_compile_options(bitwasm_signer PRIVATE -Os -Wno-unused-function)

add_library(usermod_bitwasm INTERFACE)
target_sources(usermod_bitwasm INTERFACE ${CMAKE_CURRENT_LIST_DIR}/modbitwasm.c)
target_link_libraries(usermod_bitwasm INTERFACE bitwasm_signer)
target_link_libraries(usermod INTERFACE usermod_bitwasm)
