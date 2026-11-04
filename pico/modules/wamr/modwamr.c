/* parser.wasm on WAMR's classic interpreter, for MicroPython: Instance(wasm) and its exports by name,
 * with memory() as its linear memory. One live instance: a soft reset frees Python's objects, not the pool */
#include <string.h>
#include "py/obj.h"
#include "py/objarray.h"
#include "py/runtime.h"
#include "wasm_export.h"

#ifndef WAMR_POOL_KB
#define WAMR_POOL_KB 160 /* what bitwasm-signer-pico gives parser.wasm, UR assembly included */
#endif
static char pool[WAMR_POOL_KB * 1024];
static bool runtime_up;
static wasm_module_t live_mod;
static wasm_module_inst_t live_inst;
static wasm_exec_env_t live_env;

typedef struct {
    mp_obj_base_t base;
    mp_obj_t wasm; /* the classic interpreter keeps pointers into these bytes, which it rewrote */
    wasm_module_inst_t inst;
    wasm_exec_env_t env;
} instance_t;

static mp_obj_t instance_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *args) {
    mp_arg_check_num(n_args, n_kw, 1, 1, false);
    char err[128];
    if (!runtime_up) {
        RuntimeInitArgs init;
        memset(&init, 0, sizeof(init));
        init.mem_alloc_type = Alloc_With_Pool;
        init.mem_alloc_option.pool.heap_buf = pool;
        init.mem_alloc_option.pool.heap_size = sizeof(pool);
        if (!wasm_runtime_full_init(&init)) mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("WAMR init failed"));
        runtime_up = true;
    }
    if (live_inst) {
        wasm_runtime_destroy_exec_env(live_env);
        wasm_runtime_deinstantiate(live_inst);
        wasm_runtime_unload(live_mod);
        live_env = NULL, live_inst = NULL, live_mod = NULL;
    }
    instance_t *self = mp_obj_malloc(instance_t, type);
    mp_buffer_info_t buf;
    mp_get_buffer_raise(args[0], &buf, MP_BUFFER_READ);
    self->wasm = mp_obj_new_bytearray(buf.len, buf.buf);
    mp_get_buffer_raise(self->wasm, &buf, MP_BUFFER_RW);
    if (!(live_mod = wasm_runtime_load(buf.buf, buf.len, err, sizeof(err)))) {
        mp_raise_msg_varg(&mp_type_RuntimeError, MP_ERROR_TEXT("WAMR: %s"), err);
    }
    if (!(live_inst = wasm_runtime_instantiate(live_mod, 8192, 0, err, sizeof(err)))) {
        wasm_runtime_unload(live_mod), live_mod = NULL;
        mp_raise_msg_varg(&mp_type_RuntimeError, MP_ERROR_TEXT("WAMR: %s"), err);
    }
    if (!(live_env = wasm_runtime_create_exec_env(live_inst, 8192))) {
        wasm_runtime_deinstantiate(live_inst), wasm_runtime_unload(live_mod), live_inst = NULL, live_mod = NULL;
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("WAMR exec env"));
    }
    self->inst = live_inst, self->env = live_env;
    return MP_OBJ_FROM_PTR(self);
}

static instance_t *live(mp_obj_t self_in) {
    instance_t *self = MP_OBJ_TO_PTR(self_in);
    if (self->inst != live_inst) mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("a newer Instance replaced this one"));
    return self;
}

/* call(name, *i32) -> signed i32, as bitwasm_signer.wamr's ctypes host returns it */
static mp_obj_t instance_call(size_t n_args, const mp_obj_t *args) {
    instance_t *self = live(args[0]);
    uint32_t argv[8] = {0};
    if (n_args - 2 > MP_ARRAY_SIZE(argv)) mp_raise_ValueError(MP_ERROR_TEXT("too many arguments"));
    for (size_t i = 2; i < n_args; i++) argv[i - 2] = (uint32_t)mp_obj_get_int_truncated(args[i]);
    wasm_function_inst_t f = wasm_runtime_lookup_function(self->inst, mp_obj_str_get_str(args[1]));
    if (!f) mp_raise_msg_varg(&mp_type_AttributeError, MP_ERROR_TEXT("no export %s"), mp_obj_str_get_str(args[1]));
    if (!wasm_runtime_call_wasm(self->env, f, n_args - 2, argv)) {
        const char *e = wasm_runtime_get_exception(self->inst);
        mp_raise_msg_varg(&mp_type_RuntimeError, MP_ERROR_TEXT("%s"), e ? e : "WAMR call failed");
    }
    return mp_obj_new_int((int32_t)argv[0]);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(instance_call_obj, 2, 10, instance_call);

static mp_obj_t instance_memory(mp_obj_t self_in) {
    instance_t *self = live(self_in);
    wasm_memory_inst_t mem = wasm_runtime_get_default_memory(self->inst);
    size_t size = wasm_memory_get_cur_page_count(mem) * wasm_memory_get_bytes_per_page(mem);
    return mp_obj_new_bytearray_by_ref(size, wasm_memory_get_base_address(mem));
}
static MP_DEFINE_CONST_FUN_OBJ_1(instance_memory_obj, instance_memory);

static mp_obj_t pool_info(void) {
    mem_alloc_info_t mi;
    wasm_runtime_get_mem_alloc_info(&mi);
    mp_obj_t t[3] = {mp_obj_new_int(mi.total_size), mp_obj_new_int(mi.total_free_size), mp_obj_new_int(mi.highmark_size)};
    return mp_obj_new_tuple(3, t);
}
static MP_DEFINE_CONST_FUN_OBJ_0(pool_info_obj, pool_info);

static const mp_rom_map_elem_t instance_locals[] = {
    { MP_ROM_QSTR(MP_QSTR_call), MP_ROM_PTR(&instance_call_obj) },
    { MP_ROM_QSTR(MP_QSTR_memory), MP_ROM_PTR(&instance_memory_obj) },
};
static MP_DEFINE_CONST_DICT(instance_locals_dict, instance_locals);

MP_DEFINE_CONST_OBJ_TYPE(instance_type, MP_QSTR_Instance, MP_TYPE_FLAG_NONE, make_new, instance_make_new,
                         locals_dict, &instance_locals_dict);

static const mp_rom_map_elem_t globals[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR__wamr) },
    { MP_ROM_QSTR(MP_QSTR_Instance), MP_ROM_PTR(&instance_type) },
    { MP_ROM_QSTR(MP_QSTR_pool_info), MP_ROM_PTR(&pool_info_obj) },
};
static MP_DEFINE_CONST_DICT(globals_dict, globals);

const mp_obj_module_t wamr_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&globals_dict,
};
MP_REGISTER_MODULE(MP_QSTR__wamr, wamr_module);
