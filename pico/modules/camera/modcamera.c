/* The camera and bitwasm-signer's QR reader, for MicroPython. Their 80-odd KB is borrowed from WAMR's
 * pool, which parser.wasm does not need while a QR code is being scanned (see modwamr.c) */
#include <string.h>
#include "py/obj.h"
#include "py/mperrno.h"
#include "py/runtime.h"
#include "camera.h"
#include "hardware/watchdog.h"

#define FRAME_SIZE ((size_t)CAMERA_W * CAMERA_H)
/* Without an FPU a frame that nearly reads takes seconds at the library's full budget; 15 keeps the
 * worst frame near 2.3 s, as bitwasm-signer-pico has it */
#define READ_BUDGET 15

size_t qr_reader_state_size(void);
size_t qr_reader_output_cap(void);
void qr_reader_state_init(void *state);
int32_t qr_reader_decode(void *state, const uint8_t *px, size_t w, size_t h, bool seedqr, bool animated, uint8_t *out,
                         uint32_t budget);
uint8_t *wamr_pool_borrow(size_t *size);
void wamr_pool_return(void);

static uint8_t *memory, *output;
static void *state;
static size_t memory_size;
static bool camera_up, framed;

/* The last frame captured, CAMERA_W x CAMERA_H greys, for _gfx's preview; NULL when there is none */
const uint8_t *camera_frame(void) {
    return memory && framed ? memory : NULL;
}

static void wipe_all(void) {
    if (!memory) return;
    volatile uint8_t *p = memory;
    for (size_t i = 0; i < memory_size; i++) p[i] = 0;
    memory = output = NULL, state = NULL, framed = false;
    wamr_pool_return();
}

/* Rust's panic handler. A reset keeps RAM, so the frame goes first */
void qr_reader_panic(void) {
    wipe_all();
    watchdog_reboot(0, 0, 0);
    for (;;) {
    }
}

static void need_open(void) {
    if (!memory) mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("camera not open"));
}

/* open(): borrows the pool and lays out frame | output | state */
static mp_obj_t camera_open(void) {
    if (memory) return mp_const_none;
    size_t size;
    uint8_t *pool = wamr_pool_borrow(&size);
    size_t need = FRAME_SIZE + qr_reader_output_cap() + qr_reader_state_size() + 8;
    if (!pool || size < need) {
        if (pool) wamr_pool_return();
        mp_raise_msg(&mp_type_MemoryError, MP_ERROR_TEXT("the QR reader does not fit the pool"));
    }
    memory = pool, memory_size = size;
    output = memory + FRAME_SIZE;
    state = (void *)(((uintptr_t)output + qr_reader_output_cap() + 7) & ~(uintptr_t)7);
    qr_reader_state_init(state);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(camera_open_obj, camera_open);

static mp_obj_t camera_close(void) {
    wipe_all();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(camera_close_obj, camera_close);

/* probe(): the sensor's product ID over SCCB, or None when nothing answers */
static mp_obj_t camera_probe(void) {
    uint8_t pid;
    camera_bus_init(&camera_ov7670);
    return camera_read_reg(0x0a, &pid) ? mp_obj_new_int(pid) : mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(camera_probe_obj, camera_probe);

/* The frame's QR code as bytes, None for no code, or the reader's negative code */
static mp_obj_t decode_frame(mp_int_t kind) {
    int32_t n = qr_reader_decode(state, memory, CAMERA_W, CAMERA_H, kind == 1, kind == 2, output, READ_BUDGET);
    if (n > 0) return mp_obj_new_bytes(output, (size_t)n);
    return n == 0 ? mp_const_none : mp_obj_new_int(n);
}

/* read(kind=0): captures a frame and reads it. kind 0 any, 1 SeedQR, 2 animated */
static mp_obj_t camera_read(size_t n_args, const mp_obj_t *args) {
    need_open();
    if (!camera_up) {
        /* XCLK and SCCB first: an I2C block still in reset faults the CPU on its first write */
        camera_bus_init(&camera_ov7670);
        if (!camera_init(&camera_ov7670)) mp_raise_OSError(MP_ENODEV);
        camera_up = true;
    }
    if (!camera_capture(memory, 1000)) mp_raise_OSError(MP_ETIMEDOUT);
    framed = true;
    return decode_frame(n_args ? mp_obj_get_int(args[0]) : 0);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(camera_read_obj, 0, 1, camera_read);

/* decode(image, kind=0): reads a 320x240 greyscale image given as bytes, for testing without a sensor */
static mp_obj_t camera_decode(size_t n_args, const mp_obj_t *args) {
    need_open();
    mp_buffer_info_t img;
    mp_get_buffer_raise(args[0], &img, MP_BUFFER_READ);
    if (img.len != FRAME_SIZE) mp_raise_ValueError(MP_ERROR_TEXT("a frame is 320x240 bytes"));
    memcpy(memory, img.buf, FRAME_SIZE);
    return decode_frame(n_args > 1 ? mp_obj_get_int(args[1]) : 0);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(camera_decode_obj, 1, 2, camera_decode);

/* stats(): (min, max, mean) of the last frame, to tell exposure and wiring from an unreadable code */
static mp_obj_t camera_stats(void) {
    need_open();
    uint32_t lo = 255, hi = 0, sum = 0;
    for (size_t i = 0; i < FRAME_SIZE; i++) {
        uint8_t v = memory[i];
        lo = v < lo ? v : lo, hi = v > hi ? v : hi, sum += v;
    }
    mp_obj_t t[3] = {mp_obj_new_int(lo), mp_obj_new_int(hi), mp_obj_new_int(sum / FRAME_SIZE)};
    return mp_obj_new_tuple(3, t);
}
static MP_DEFINE_CONST_FUN_OBJ_0(camera_stats_obj, camera_stats);

static const mp_rom_map_elem_t globals[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR__camera) },
    { MP_ROM_QSTR(MP_QSTR_open), MP_ROM_PTR(&camera_open_obj) },
    { MP_ROM_QSTR(MP_QSTR_close), MP_ROM_PTR(&camera_close_obj) },
    { MP_ROM_QSTR(MP_QSTR_probe), MP_ROM_PTR(&camera_probe_obj) },
    { MP_ROM_QSTR(MP_QSTR_read), MP_ROM_PTR(&camera_read_obj) },
    { MP_ROM_QSTR(MP_QSTR_decode), MP_ROM_PTR(&camera_decode_obj) },
    { MP_ROM_QSTR(MP_QSTR_stats), MP_ROM_PTR(&camera_stats_obj) },
    { MP_ROM_QSTR(MP_QSTR_WIDTH), MP_ROM_INT(CAMERA_W) },
    { MP_ROM_QSTR(MP_QSTR_HEIGHT), MP_ROM_INT(CAMERA_H) },
};
static MP_DEFINE_CONST_DICT(globals_dict, globals);

const mp_obj_module_t camera_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&globals_dict,
};
MP_REGISTER_MODULE(MP_QSTR__camera, camera_module);
