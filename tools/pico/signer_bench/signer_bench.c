/* signer.wasm on the RP2350's WAMR classic interpreter: time and pool use of what SeedSigner calls.
 * The BIP39 test vector seed; results go to `bench` in RAM, read over SWD */
#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "wasm_export.h"
#include "signer_wasm.h"

#define MN "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
#define ADDR6 "tb1q4e9q5taxnsvc6m0uxv6h75mkzvnkxeqkckuztr" /* m/84'/1'/0'/0/6 */

static char pool[POOL_KB * 1024];
static uint8_t wasm_rw[sizeof(signer_wasm)]; /* the classic interpreter rewrites the bytecode on load */

struct bench {
    uint32_t magic, stage, err;
    uint32_t us_load, us_inst, us_init, us_seed, us_xpub, us_addr0, us_addr1, us_addr99, us_find;
    int32_t find_rc;
    uint32_t fingerprint, pool_total, pool_free, pool_highmark, mem_pages;
    char addr0[80], err_text[64];
};
volatile struct bench bench;

static wasm_module_inst_t inst;
static wasm_exec_env_t env;

static int call(const char *name, uint32_t argc, uint32_t *argv) {
    wasm_function_inst_t f = wasm_runtime_lookup_function(inst, name);
    if (!f || !wasm_runtime_call_wasm(env, f, argc, argv)) {
        strncpy((char *)bench.err_text, f ? wasm_runtime_get_exception(inst) : name, sizeof(bench.err_text) - 1);
        return 0;
    }
    return 1;
}

static uint8_t *ptr(const char *fn) {
    uint32_t a[1] = {0};
    return call(fn, 0, a) ? wasm_runtime_addr_app_to_native(inst, a[0]) : NULL;
}

#define T(field, expr) do { uint64_t t0 = time_us_64(); if (!(expr)) { bench.err = __LINE__; return; } \
    bench.field = (uint32_t)(time_us_64() - t0); } while (0)

static void run(void) {
    RuntimeInitArgs args;
    char err[128];
    wasm_module_t mod;
    uint32_t a[4];
    mem_alloc_info_t mi;

    memset(&args, 0, sizeof(args));
    args.mem_alloc_type = Alloc_With_Pool;
    args.mem_alloc_option.pool.heap_buf = pool;
    args.mem_alloc_option.pool.heap_size = sizeof(pool);
    bench.stage = 1;
    if (!wasm_runtime_full_init(&args)) { bench.err = __LINE__; return; }
    memcpy(wasm_rw, signer_wasm, sizeof(signer_wasm));
    T(us_load, (mod = wasm_runtime_load(wasm_rw, sizeof(wasm_rw), err, sizeof(err))));
    bench.stage = 2;
    T(us_inst, (inst = wasm_runtime_instantiate(mod, 8192, 0, err, sizeof(err))));
    if (!inst) strncpy((char *)bench.err_text, err, sizeof(bench.err_text) - 1);
    env = wasm_runtime_create_exec_env(inst, 8192);
    bench.mem_pages = wasm_memory_get_cur_page_count(wasm_runtime_get_default_memory(inst));
    bench.stage = 3;
    a[0] = 1; /* testnet */
    T(us_init, call("signer_init", 1, a) && a[0]);
    memcpy(ptr("signer_input"), MN, sizeof(MN) - 1);
    a[0] = sizeof(MN) - 1, a[1] = 0;
    bench.stage = 4;
    T(us_seed, call("signer_seed_from_mnemonic", 2, a) && a[0]);
    call("signer_fingerprint", 0, a), bench.fingerprint = a[0];
    a[0] = 84, a[1] = 0;
    bench.stage = 5;
    T(us_xpub, call("signer_xpub", 2, a) && a[0] == 0);
    a[0] = 84, a[1] = 0, a[2] = 0, a[3] = 0;
    bench.stage = 6;
    T(us_addr0, call("signer_address", 4, a) && a[0] == 0);
    strncpy((char *)bench.addr0, (char *)ptr("signer_address_output"), sizeof(bench.addr0) - 1);
    a[0] = 84, a[1] = 0, a[2] = 0, a[3] = 1;
    T(us_addr1, call("signer_address", 4, a) && a[0] == 0);
    a[0] = 86, a[1] = 0, a[2] = 1, a[3] = 99;
    T(us_addr99, call("signer_address", 4, a) && a[0] == 0);
    memcpy(ptr("signer_input"), ADDR6, sizeof(ADDR6) - 1);
    a[0] = sizeof(ADDR6) - 1, a[1] = 0, a[2] = 20;
    bench.stage = 7;
    T(us_find, call("signer_find_address", 3, a));
    bench.find_rc = (int32_t)a[0];
    wasm_runtime_get_mem_alloc_info(&mi);
    bench.pool_total = mi.total_size, bench.pool_free = mi.total_free_size, bench.pool_highmark = mi.highmark_size;
    bench.stage = 100;
}

int main(void) {
    stdio_init_all();
    bench.magic = 0x5eed5167;
    run();
    printf("stage %lu err %lu seed %lu us addr %lu us\n", (unsigned long)bench.stage, (unsigned long)bench.err,
           (unsigned long)bench.us_seed, (unsigned long)bench.us_addr0);
    for (;;) tight_loop_contents();
}
