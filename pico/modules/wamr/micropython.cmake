# WAMR 2.4.5's classic interpreter for the rp2 port, configured as bitwasm-signer-pico's, on its platform
# layer (platform/, copied from bitwasm-signer-pico 7093d78). WAMR_ROOT is a checkout at that tag
set(WAMR_ROOT_DIR $ENV{WAMR_ROOT})
if(NOT WAMR_ROOT_DIR)
  message(FATAL_ERROR "set WAMR_ROOT to a wasm-micro-runtime checkout at WAMR-2.4.5")
endif()
set(SHARED_PLATFORM_CONFIG ${CMAKE_CURRENT_LIST_DIR}/platform/shared_platform.cmake)
set(WAMR_BUILD_PLATFORM rp2350)
set(WAMR_BUILD_TARGET RISCV32_ILP32)
set(WAMR_BUILD_AOT 0)
set(WAMR_BUILD_INTERP 1)
set(WAMR_BUILD_FAST_INTERP 0)
set(WAMR_BUILD_LIBC_BUILTIN 0)
set(WAMR_BUILD_LIBC_WASI 0)
set(WAMR_BUILD_SIMD 0)
set(WAMR_BUILD_REF_TYPES 0)
set(WAMR_DISABLE_HW_BOUND_CHECK 1)
set(saved_flags "${CMAKE_C_FLAGS}")
include(${WAMR_ROOT_DIR}/build-scripts/runtime_lib.cmake)
set(CMAKE_C_FLAGS "${saved_flags}")  # runtime_lib.cmake appends -std=gnu99, which pico-sdk cannot build with

add_library(wamr_runtime STATIC ${WAMR_RUNTIME_LIB_SOURCE})
target_compile_definitions(wamr_runtime PRIVATE PICO_BUILD=1)
# Unused functions, some calling platform hooks the RP2350 layer leaves out, go at link time as in bitwasm-signer-pico
target_compile_options(wamr_runtime PRIVATE -Wno-error -ffunction-sections -fdata-sections)
target_link_libraries(wamr_runtime PRIVATE pico_time)

add_library(usermod_wamr INTERFACE)
target_sources(usermod_wamr INTERFACE ${CMAKE_CURRENT_LIST_DIR}/modwamr.c)
target_include_directories(usermod_wamr INTERFACE ${WAMR_ROOT_DIR}/core/iwasm/include)
target_link_libraries(usermod_wamr INTERFACE wamr_runtime)
target_link_libraries(usermod INTERFACE usermod_wamr)
