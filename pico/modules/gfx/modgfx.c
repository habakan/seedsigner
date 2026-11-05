/* The 240x240 canvas SeedSigner's screens draw on, and the ST7789 it goes to. One byte a pixel keeps it
 * to 57.6 KB, out of MicroPython's heap: a 6x6x6 colour cube and 40 greys, as SeedSigner's palette is greys */
#include <string.h>
#include "py/obj.h"
#include "py/objarray.h"
#include "py/runtime.h"
#include "board_pins.h"
#include "hardware/gpio.h"
#include "hardware/spi.h"
#include "pico/time.h"

#define W 240
#define H 240
#define LCD_SPI spi0
/* Modest for jumper leads, as bitwasm-signer-pico has it; the ST7789 takes up to 62.5 MHz */
#define LCD_BAUD (40 * 1000 * 1000)

static uint8_t canvas[W * H];
static uint16_t rgb565[256];
static uint8_t rgb[256][3];
static bool lcd_up, palette_up;

/* Index 0-215 the cube, 36r + 6g + b of levels 0, 51, ..., 255; 216-255 greys 0 to 255 */
static void palette_init(void) {
    for (int i = 0; i < 256; i++) {
        int r, g, b;
        if (i < 216) r = i / 36 * 51, g = i / 6 % 6 * 51, b = i % 6 * 51;
        else r = g = b = (i - 216) * 255 / 39;
        rgb[i][0] = (uint8_t)r, rgb[i][1] = (uint8_t)g, rgb[i][2] = (uint8_t)b;
        rgb565[i] = (uint16_t)(((r * 31 + 127) / 255) << 11 | ((g * 63 + 127) / 255) << 5 | ((b * 31 + 127) / 255));
    }
    palette_up = true;
}

static uint8_t encode(int r, int g, int b) {
    int hi = r > g ? (r > b ? r : b) : (g > b ? g : b), lo = r < g ? (r < b ? r : b) : (g < b ? g : b);
    if (hi - lo <= 12) return (uint8_t)(216 + ((r + g + b) * 39 + 382) / 765);
    return (uint8_t)(36 * ((r + 25) / 51) + 6 * ((g + 25) / 51) + (b + 25) / 51);
}

static void cmd(uint8_t c, const uint8_t *data, unsigned int n) {
    gpio_put(PIN_LCD_DC, 0);
    spi_write_blocking(LCD_SPI, &c, 1);
    gpio_put(PIN_LCD_DC, 1);
    if (n) spi_write_blocking(LCD_SPI, data, n);
}

/* bitwasm-signer-pico a6a5b91's st7789_init: CS tied low (so SPI mode 3), RES tied high, IPS inverted */
static void lcd_init(void) {
    static const uint8_t colmod = 0x55, madctl = 0x00;
    spi_init(LCD_SPI, LCD_BAUD);
    spi_set_format(LCD_SPI, 8, SPI_CPOL_1, SPI_CPHA_1, SPI_MSB_FIRST);
    gpio_set_function(PIN_LCD_SCK, GPIO_FUNC_SPI);
    gpio_set_function(PIN_LCD_MOSI, GPIO_FUNC_SPI);
    gpio_init(PIN_LCD_DC);
    gpio_set_dir(PIN_LCD_DC, GPIO_OUT);
    cmd(0x01, NULL, 0);
    sleep_ms(150);
    cmd(0x11, NULL, 0);
    sleep_ms(120);
    cmd(0x3a, &colmod, 1);
    cmd(0x36, &madctl, 1);
    cmd(0x21, NULL, 0);
    cmd(0x13, NULL, 0);
    cmd(0x29, NULL, 0);
    if (!palette_up) palette_init();
    lcd_up = true;
}

static inline int clampi(int v, int lo, int hi) {
    return v < lo ? lo : v > hi ? hi : v;
}

static inline uint8_t blend(uint8_t bg, uint8_t fg, int a /* 0..15 */) {
    const uint8_t *p = rgb[bg], *q = rgb[fg];
    return encode((p[0] * (15 - a) + q[0] * a + 7) / 15, (p[1] * (15 - a) + q[1] * a + 7) / 15,
                  (p[2] * (15 - a) + q[2] * a + 7) / 15);
}

/* show(x0=0, y0=0, x1=240, y1=240): sends that part of the canvas */
static mp_obj_t gfx_show(size_t n_args, const mp_obj_t *args) {
    if (!lcd_up) lcd_init();
    int x0 = n_args > 0 ? clampi(mp_obj_get_int(args[0]), 0, W) : 0;
    int y0 = n_args > 1 ? clampi(mp_obj_get_int(args[1]), 0, H) : 0;
    int x1 = n_args > 2 ? clampi(mp_obj_get_int(args[2]), 0, W) : W;
    int y1 = n_args > 3 ? clampi(mp_obj_get_int(args[3]), 0, H) : H;
    if (x1 <= x0 || y1 <= y0) return mp_const_none;
    uint8_t caset[4] = {0, (uint8_t)x0, 0, (uint8_t)(x1 - 1)}, raset[4] = {0, (uint8_t)y0, 0, (uint8_t)(y1 - 1)};
    cmd(0x2a, caset, 4);
    cmd(0x2b, raset, 4);
    cmd(0x2c, NULL, 0);
    uint8_t line[W * 2];
    for (int y = y0; y < y1; y++) {
        const uint8_t *row = canvas + y * W;
        for (int x = x0; x < x1; x++) {
            uint16_t p = rgb565[row[x]];
            line[2 * (x - x0)] = (uint8_t)(p >> 8), line[2 * (x - x0) + 1] = (uint8_t)p;
        }
        spi_write_blocking(LCD_SPI, line, (size_t)(x1 - x0) * 2);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_show_obj, 0, 4, gfx_show);

/* fill(x0, y0, x1, y1, c): x1 and y1 exclusive, clipped to the canvas */
static mp_obj_t gfx_fill(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    int x0 = clampi(mp_obj_get_int(args[0]), 0, W), y0 = clampi(mp_obj_get_int(args[1]), 0, H);
    int x1 = clampi(mp_obj_get_int(args[2]), 0, W), y1 = clampi(mp_obj_get_int(args[3]), 0, H);
    uint8_t c = (uint8_t)mp_obj_get_int(args[4]);
    for (int y = y0; y < y1; y++) memset(canvas + y * W + x0, c, (size_t)(x1 > x0 ? x1 - x0 : 0));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_fill_obj, 5, 5, gfx_fill);

/* glyph(x, y, w, h, alpha, c, cx0, cy0, cx1, cy1): blends a 4-bit alpha bitmap (two pixels a byte, high
 * nibble first, rows padded to whole bytes) in colour c, clipped to the canvas and to the clip box */
static mp_obj_t gfx_glyph(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    int x = mp_obj_get_int(args[0]), y = mp_obj_get_int(args[1]);
    int w = mp_obj_get_int(args[2]), h = mp_obj_get_int(args[3]);
    mp_buffer_info_t a;
    mp_get_buffer_raise(args[4], &a, MP_BUFFER_READ);
    uint8_t c = (uint8_t)mp_obj_get_int(args[5]);
    int cx0 = clampi(mp_obj_get_int(args[6]), 0, W), cy0 = clampi(mp_obj_get_int(args[7]), 0, H);
    int cx1 = clampi(mp_obj_get_int(args[8]), 0, W), cy1 = clampi(mp_obj_get_int(args[9]), 0, H);
    int stride = (w + 1) / 2;
    if (!palette_up) palette_init();
    if ((size_t)(stride * h) > a.len) mp_raise_ValueError(MP_ERROR_TEXT("glyph bitmap too short"));
    const uint8_t *src = a.buf;
    for (int j = 0; j < h; j++) {
        int py = y + j;
        if (py < cy0 || py >= cy1) continue;
        for (int i = 0; i < w; i++) {
            int px = x + i;
            if (px < cx0 || px >= cx1) continue;
            uint8_t v = src[j * stride + i / 2];
            int al = (i & 1) ? (v & 15) : (v >> 4);
            if (!al) continue;
            uint8_t *d = canvas + py * W + px;
            *d = al == 15 ? c : blend(*d, c, al);
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_glyph_obj, 10, 10, gfx_glyph);

/* blit(src, w, h, x, y): pastes w x h palette indices at (x, y), clipped */
static mp_obj_t gfx_blit(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    mp_buffer_info_t s;
    mp_get_buffer_raise(args[0], &s, MP_BUFFER_READ);
    int w = mp_obj_get_int(args[1]), h = mp_obj_get_int(args[2]);
    int x = mp_obj_get_int(args[3]), y = mp_obj_get_int(args[4]);
    if ((size_t)(w * h) > s.len) mp_raise_ValueError(MP_ERROR_TEXT("image too short"));
    for (int j = 0; j < h; j++) {
        int py = y + j;
        if (py < 0 || py >= H) continue;
        int i0 = x < 0 ? -x : 0, i1 = x + w > W ? W - x : w;
        if (i1 > i0) memcpy(canvas + py * W + x + i0, (const uint8_t *)s.buf + j * w + i0, (size_t)(i1 - i0));
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_blit_obj, 5, 5, gfx_blit);

/* colour(r, g, b): the palette index for that colour */
static mp_obj_t gfx_colour(mp_obj_t r, mp_obj_t g, mp_obj_t b) {
    return mp_obj_new_int(encode(mp_obj_get_int(r), mp_obj_get_int(g), mp_obj_get_int(b)));
}
static MP_DEFINE_CONST_FUN_OBJ_3(gfx_colour_obj, gfx_colour);

/* canvas(): the canvas itself as a bytearray, for the odd pixel Python sets */
static mp_obj_t gfx_canvas(void) {
    return mp_obj_new_bytearray_by_ref(sizeof(canvas), canvas);
}
static MP_DEFINE_CONST_FUN_OBJ_0(gfx_canvas_obj, gfx_canvas);

static const mp_rom_map_elem_t globals[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR__gfx) },
    { MP_ROM_QSTR(MP_QSTR_show), MP_ROM_PTR(&gfx_show_obj) },
    { MP_ROM_QSTR(MP_QSTR_fill), MP_ROM_PTR(&gfx_fill_obj) },
    { MP_ROM_QSTR(MP_QSTR_glyph), MP_ROM_PTR(&gfx_glyph_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit), MP_ROM_PTR(&gfx_blit_obj) },
    { MP_ROM_QSTR(MP_QSTR_canvas), MP_ROM_PTR(&gfx_canvas_obj) },
    { MP_ROM_QSTR(MP_QSTR_colour), MP_ROM_PTR(&gfx_colour_obj) },
    { MP_ROM_QSTR(MP_QSTR_WIDTH), MP_ROM_INT(W) },
    { MP_ROM_QSTR(MP_QSTR_HEIGHT), MP_ROM_INT(H) },
};
static MP_DEFINE_CONST_DICT(globals_dict, globals);

const mp_obj_module_t gfx_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&globals_dict,
};
MP_REGISTER_MODULE(MP_QSTR__gfx, gfx_module);
