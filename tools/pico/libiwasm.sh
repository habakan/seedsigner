#!/bin/sh
# libiwasm for the tests, configured as bitwasm-signer-pico's WAMR: classic interpreter and software
# bounds checks. The hardware checks' guard pages cannot be set up on a Python thread's stack on macOS
set -e
WAMR_ROOT=${WAMR_ROOT:-../bitwasm-signer/third_party/wasm-micro-runtime}
test "$(git -C "$WAMR_ROOT" rev-parse HEAD)" = 25bd7eb63e828e4bd242cc9b38d260b4b31c6605
case "$(uname -s)" in Darwin) platform=darwin ;; *) platform=linux ;; esac
cmake -S "$WAMR_ROOT/product-mini/platforms/$platform" -B build/wamr -DCMAKE_BUILD_TYPE=Release \
  -DWAMR_BUILD_INTERP=1 -DWAMR_BUILD_FAST_INTERP=0 -DWAMR_BUILD_DEBUG_INTERP=0 \
  -DWAMR_BUILD_AOT=0 -DWAMR_BUILD_JIT=0 -DWAMR_BUILD_SIMD=0 \
  -DWAMR_BUILD_LIBC_BUILTIN=0 -DWAMR_BUILD_LIBC_WASI=0 -DBUILD_SHARED_LIBS=ON \
  -DWAMR_DISABLE_HW_BOUND_CHECK=1 >/dev/null
cmake --build build/wamr --parallel >/dev/null
ls build/wamr/libiwasm.*
