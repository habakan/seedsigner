/* SeedSigner's screens drawn a band of rows at a time (pico/lib/PIL replays them per band) and sent to the
 * ST7789: a 57.6 KB canvas is heap SeedSigner needs. One byte a pixel, a colour cube and 40 greys */
#include <string.h>
#include "py/obj.h"
#include "py/objarray.h"
#include "py/runtime.h"
#include "qrcodegen.h"
#include "board_pins.h"
#include "hardware/gpio.h"
#include "hardware/spi.h"
#include "pico/time.h"

#define W 240
#define H 240
#define LCD_SPI spi0
/* Modest for jumper leads, as bitwasm-signer-pico has it; the ST7789 takes up to 62.5 MHz */
#define LCD_BAUD (40 * 1000 * 1000)

#define BAND 40
static uint8_t band[W * BAND];
static int band_y0;
#define BAND_Y1 (band_y0 + BAND < H ? band_y0 + BAND : H)
#define PX(x, y) (band + ((y) - band_y0) * W + (x))
/* Clip boxes come in screen rows; drawing lands only in the band's */
#define CLIP_Y(v) clampi(mp_obj_get_int(v), band_y0, BAND_Y1)
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

/* band(y0): the band now drawn on is rows y0 to y0 + BAND; its height */
static mp_obj_t gfx_band(mp_obj_t y0) {
    band_y0 = clampi(mp_obj_get_int(y0), 0, H - 1);
    return MP_OBJ_NEW_SMALL_INT(BAND_Y1 - band_y0);
}
static MP_DEFINE_CONST_FUN_OBJ_1(gfx_band_obj, gfx_band);

/* show(x0=0, y0=0, x1=240, y1=240): sends that part of the band */
static mp_obj_t gfx_show(size_t n_args, const mp_obj_t *args) {
    if (!lcd_up) lcd_init();
    int x0 = n_args > 0 ? clampi(mp_obj_get_int(args[0]), 0, W) : 0;
    int y0 = n_args > 1 ? CLIP_Y(args[1]) : band_y0;
    int x1 = n_args > 2 ? clampi(mp_obj_get_int(args[2]), 0, W) : W;
    int y1 = n_args > 3 ? CLIP_Y(args[3]) : BAND_Y1;
    if (x1 <= x0 || y1 <= y0) return mp_const_none;
    uint8_t caset[4] = {0, (uint8_t)x0, 0, (uint8_t)(x1 - 1)}, raset[4] = {0, (uint8_t)y0, 0, (uint8_t)(y1 - 1)};
    cmd(0x2a, caset, 4);
    cmd(0x2b, raset, 4);
    cmd(0x2c, NULL, 0);
    uint8_t line[W * 2];
    for (int y = y0; y < y1; y++) {
        const uint8_t *row = PX(0, y);
        for (int x = x0; x < x1; x++) {
            uint16_t p = rgb565[row[x]];
            line[2 * (x - x0)] = (uint8_t)(p >> 8), line[2 * (x - x0) + 1] = (uint8_t)p;
        }
        spi_write_blocking(LCD_SPI, line, (size_t)(x1 - x0) * 2);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_show_obj, 0, 4, gfx_show);

/* fill(x0, y0, x1, y1, c): x1 and y1 exclusive, clipped to the band */
static mp_obj_t gfx_fill(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    int x0 = clampi(mp_obj_get_int(args[0]), 0, W), y0 = CLIP_Y(args[1]);
    int x1 = clampi(mp_obj_get_int(args[2]), 0, W), y1 = CLIP_Y(args[3]);
    uint8_t c = (uint8_t)mp_obj_get_int(args[4]);
    for (int y = y0; y < y1; y++) memset(PX(x0, y), c, (size_t)(x1 > x0 ? x1 - x0 : 0));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_fill_obj, 5, 5, gfx_fill);

/* glyph(x, y, w, h, alpha, c, cx0, cy0, cx1, cy1): blends a 4-bit alpha bitmap (two pixels a byte, high
 * nibble first, rows padded to whole bytes) in colour c, clipped to the band and to the clip box */
static mp_obj_t gfx_glyph(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    int x = mp_obj_get_int(args[0]), y = mp_obj_get_int(args[1]);
    int w = mp_obj_get_int(args[2]), h = mp_obj_get_int(args[3]);
    mp_buffer_info_t a;
    mp_get_buffer_raise(args[4], &a, MP_BUFFER_READ);
    uint8_t c = (uint8_t)mp_obj_get_int(args[5]);
    int cx0 = clampi(mp_obj_get_int(args[6]), 0, W), cy0 = CLIP_Y(args[7]);
    int cx1 = clampi(mp_obj_get_int(args[8]), 0, W), cy1 = CLIP_Y(args[9]);
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
            uint8_t *d = PX(px, py);
            *d = al == 15 ? c : blend(*d, c, al);
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_glyph_obj, 10, 10, gfx_glyph);

/* Rounded rectangles and ellipses, a row at a time as pico/lib/PIL/ImageDraw.py had them in Python: only the
 * rows in the clip are worked out, where Python made every row for every band */
#include <math.h>
typedef struct { int x0, y0, x1, y1, r; bool ellipse; } shape_t;

/* Row y's span of the shape, inclusive; false where the shape has no such row */
static bool shape_row(const shape_t *sh, int y, int *a, int *b) {
    if (y < sh->y0 || y > sh->y1 || sh->x1 < sh->x0) return false;
    if (sh->ellipse) {
        double cx = (sh->x0 + sh->x1) / 2.0, cy = (sh->y0 + sh->y1) / 2.0;
        double rx = (sh->x1 - sh->x0 + 1) / 2.0, ry = (sh->y1 - sh->y0 + 1) / 2.0;
        double t = ry ? (y + 0.5 - (cy + 0.5)) / ry : 0;
        if (t * t > 1) return false;
        double half = rx * sqrt(1 - t * t);
        *a = (int)(cx + 0.5 - half + 0.5), *b = (int)(cx + 0.5 + half - 0.5);
        return true;
    }
    int k = y - sh->y0 < sh->y1 - y ? y - sh->y0 : sh->y1 - y, i = 0;
    if (k < sh->r) {
        double d = sh->r - k - 0.5;
        i = d * d < (double)sh->r * sh->r ? sh->r - (int)(sqrt((double)sh->r * sh->r - d * d) + 0.5) : sh->r;
    }
    *a = sh->x0 + i, *b = sh->x1 - i;
    return true;
}

static void span(int y, int a, int b, uint8_t c, int cx0, int cx1) {
    a = a < cx0 ? cx0 : a, b = b >= cx1 ? cx1 - 1 : b;
    if (b >= a) memset(PX(a, y), c, (size_t)(b - a + 1));
}

static int clamp_r(int r, int x0, int y0, int x1, int y1) {
    int m = (x1 - x0 + 1) / 2 < (y1 - y0 + 1) / 2 ? (x1 - x0 + 1) / 2 : (y1 - y0 + 1) / 2;
    return r < 0 ? 0 : r > m ? m : r;
}

/* shape(ellipse, x0, y0, x1, y1, r, fill, outline, width, dx, dy, cx0, cy0, cx1, cy1): fill and outline are
 * palette indices or -1; the outline is the shape less the one inset by width */
static mp_obj_t gfx_shape(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    bool ell = mp_obj_is_true(args[0]);
    int x0 = mp_obj_get_int(args[1]), y0 = mp_obj_get_int(args[2]), x1 = mp_obj_get_int(args[3]);
    int y1 = mp_obj_get_int(args[4]), r = mp_obj_get_int(args[5]);
    int fill = mp_obj_get_int(args[6]), outline = mp_obj_get_int(args[7]), w = mp_obj_get_int(args[8]);
    int dx = mp_obj_get_int(args[9]), dy = mp_obj_get_int(args[10]);
    int cx0 = clampi(mp_obj_get_int(args[11]), 0, W), cy0 = CLIP_Y(args[12]);
    int cx1 = clampi(mp_obj_get_int(args[13]), 0, W), cy1 = CLIP_Y(args[14]);
    shape_t outer = {x0, y0, x1, y1, clamp_r(r, x0, y0, x1, y1), ell};
    shape_t inner = {x0 + w, y0 + w, x1 - w, y1 - w, 0, ell};
    inner.r = clamp_r(r - w > 0 ? r - w : 0, inner.x0, inner.y0, inner.x1, inner.y1);
    bool ring = outline >= 0 && w > 0;
    for (int py = cy0; py < cy1; py++) {
        int y = py - dy, a, b, ia, ib;
        if (!shape_row(&outer, y, &a, &b)) continue;
        if (!ring) {
            if (fill >= 0) span(py, dx + a, dx + b, (uint8_t)fill, cx0, cx1);
            continue;
        }
        if (shape_row(&inner, y, &ia, &ib) && ia <= ib) {
            span(py, dx + a, dx + ia - 1, (uint8_t)outline, cx0, cx1);
            span(py, dx + ib + 1, dx + b, (uint8_t)outline, cx0, cx1);
            if (fill >= 0) span(py, dx + ia, dx + ib, (uint8_t)fill, cx0, cx1);
        } else {
            span(py, dx + a, dx + b, (uint8_t)outline, cx0, cx1);
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_shape_obj, 15, 15, gfx_shape);

/* shade(x0, y0, x1, y1, c, a, cx0, cy0, cx1, cy1): blends colour c at a/15 over what the box holds, x1 and
 * y1 exclusive: a translucent overlay, as SeedSigner dims all but a SeedQR zone */
static mp_obj_t gfx_shade(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    int x0 = mp_obj_get_int(args[0]), y0 = mp_obj_get_int(args[1]), x1 = mp_obj_get_int(args[2]), y1 = mp_obj_get_int(args[3]);
    uint8_t c = (uint8_t)mp_obj_get_int(args[4]);
    int a = clampi(mp_obj_get_int(args[5]), 0, 15);
    int cx0 = clampi(mp_obj_get_int(args[6]), 0, W), cy0 = CLIP_Y(args[7]);
    int cx1 = clampi(mp_obj_get_int(args[8]), 0, W), cy1 = CLIP_Y(args[9]);
    x0 = x0 > cx0 ? x0 : cx0, y0 = y0 > cy0 ? y0 : cy0, x1 = x1 < cx1 ? x1 : cx1, y1 = y1 < cy1 ? y1 : cy1;
    if (!palette_up) palette_init();
    for (int y = y0; y < y1; y++)
        for (int x = x0; x < x1; x++) {
            uint8_t *d = PX(x, y);
            *d = a == 15 ? c : blend(*d, c, a);
        }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_shade_obj, 10, 10, gfx_shade);

/* glyphs(placed, bitmaps, c, dx, dy, cx0, cy0, cx1, cy1): a line of text, as ImageDraw placed its glyphs when it
 * recorded it, `<hhBBI` (x, y, w, h, offset into bitmaps) each, blended like glyph() */
static mp_obj_t gfx_glyphs(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    mp_buffer_info_t pl, bm;
    mp_get_buffer_raise(args[0], &pl, MP_BUFFER_READ);
    mp_get_buffer_raise(args[1], &bm, MP_BUFFER_READ);
    uint8_t c = (uint8_t)mp_obj_get_int(args[2]);
    int dx = mp_obj_get_int(args[3]), dy = mp_obj_get_int(args[4]);
    int cx0 = clampi(mp_obj_get_int(args[5]), 0, W), cy0 = CLIP_Y(args[6]);
    int cx1 = clampi(mp_obj_get_int(args[7]), 0, W), cy1 = CLIP_Y(args[8]);
    if (!palette_up) palette_init();
    const uint8_t *p = pl.buf, *bits = bm.buf;
    for (size_t k = 0; k + 10 <= pl.len; k += 10) {
        int x = dx + (int16_t)(p[k] | p[k + 1] << 8), y = dy + (int16_t)(p[k + 2] | p[k + 3] << 8);
        int w = p[k + 4], h = p[k + 5], stride = (w + 1) / 2;
        uint32_t off = p[k + 6] | p[k + 7] << 8 | p[k + 8] << 16 | (uint32_t)p[k + 9] << 24;
        if (y >= cy1 || y + h <= cy0 || x >= cx1 || x + w <= cx0) continue;
        if (off + (size_t)stride * h > bm.len) mp_raise_ValueError(MP_ERROR_TEXT("glyph bitmap too short"));
        const uint8_t *src = bits + off;
        for (int j = 0; j < h; j++) {
            int py = y + j;
            if (py < cy0 || py >= cy1) continue;
            for (int i = 0; i < w; i++) {
                int px = x + i;
                if (px < cx0 || px >= cx1) continue;
                uint8_t v = src[j * stride + i / 2];
                int al = (i & 1) ? (v & 15) : (v >> 4);
                if (!al) continue;
                uint8_t *d = PX(px, py);
                *d = al == 15 ? c : blend(*d, c, al);
            }
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_glyphs_obj, 9, 9, gfx_glyphs);

/* blit(src, w, h, x, y, cx0, cy0, cx1, cy1): pastes w x h palette indices at (x, y), clipped to the box */
static mp_obj_t gfx_blit(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    mp_buffer_info_t s;
    mp_get_buffer_raise(args[0], &s, MP_BUFFER_READ);
    int w = mp_obj_get_int(args[1]), h = mp_obj_get_int(args[2]);
    int x = mp_obj_get_int(args[3]), y = mp_obj_get_int(args[4]);
    int cx0 = clampi(mp_obj_get_int(args[5]), 0, W), cy0 = CLIP_Y(args[6]);
    int cx1 = clampi(mp_obj_get_int(args[7]), 0, W), cy1 = CLIP_Y(args[8]);
    if ((size_t)(w * h) > s.len) mp_raise_ValueError(MP_ERROR_TEXT("image too short"));
    for (int j = 0; j < h; j++) {
        int py = y + j;
        if (py < cy0 || py >= cy1) continue;
        int i0 = x < cx0 ? cx0 - x : 0, i1 = x + w > cx1 ? cx1 - x : w;
        if (i1 > i0) memcpy(PX(x + i0, py), (const uint8_t *)s.buf + j * w + i0, (size_t)(i1 - i0));
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_blit_obj, 9, 9, gfx_blit);

const uint8_t *camera_frame(void);

/* camera(x, y, cx0, cy0, cx1, cy1): the middle 240 x 240 of the camera's last 320 x 240 frame at (x, y), in
 * the greys, clipped to the box; black without a frame. The frame stays in the camera's memory */
static mp_obj_t gfx_camera(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    int x = mp_obj_get_int(args[0]), y = mp_obj_get_int(args[1]);
    int cx0 = clampi(mp_obj_get_int(args[2]), 0, W), cy0 = CLIP_Y(args[3]);
    int cx1 = clampi(mp_obj_get_int(args[4]), 0, W), cy1 = CLIP_Y(args[5]);
    const uint8_t *f = camera_frame();
    for (int py = cy0 > y ? cy0 : y; py < cy1 && py < y + 240; py++) {
        uint8_t *row = PX(0, py);
        const uint8_t *src = f ? f + (size_t)(py - y) * 320 + 40 - x : NULL;
        for (int px = cx0 > x ? cx0 : x; px < cx1 && px < x + 240; px++)
            row[px] = src ? (uint8_t)(216 + (src[px] * 39 + 127) / 255) : 216;
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_camera_obj, 6, 6, gfx_camera);

/* save(x0, y0, x1, y1): that part of the band run-length encoded, (count, index) pairs row by row: a
 * screenshot, band by band, for pico/tests/drive.py */
static mp_obj_t gfx_save(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    int x0 = clampi(mp_obj_get_int(args[0]), 0, W), y0 = CLIP_Y(args[1]);
    int x1 = clampi(mp_obj_get_int(args[2]), 0, W), y1 = CLIP_Y(args[3]);
    size_t n = 0;
    for (int pass = 0; pass < 2; pass++) {
        uint8_t *out = NULL;
        vstr_t v;
        if (pass) vstr_init_len(&v, n), out = (uint8_t *)v.buf;
        size_t k = 0;
        for (int y = y0; y < y1; y++) {
            const uint8_t *row = PX(0, y);
            for (int x = x0; x < x1;) {
                int run = 1;
                while (x + run < x1 && run < 255 && row[x + run] == row[x]) run++;
                if (out) out[k] = (uint8_t)run, out[k + 1] = row[x];
                k += 2, x += run;
            }
        }
        if (!pass) n = k;
        else return mp_obj_new_bytes_from_vstr(&v);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_save_obj, 4, 4, gfx_save);

/* Static, not on the heap, which fragments. Version 25 holds 1273 bytes, past anything SeedSigner shows in one
 * code; the text goes in qr_out, which qrcodegen reads it from before writing the code there */
#define QR_VERSION_MAX 25
#define QR_LEN qrcodegen_BUFFER_LEN_FOR_VERSION(QR_VERSION_MAX)
static uint8_t qr_temp[QR_LEN], qr_out[QR_LEN + 1];

/* qr_encode(data): a str (numeric, alphanumeric or byte mode, whichever fits it) or bytes as a QR code at
 * level L in the smallest version, as SeedSigner's qrcode and qrencode make it; qrcodegen's buffer, trimmed */
static mp_obj_t gfx_qr_encode(mp_obj_t data) {
    bool ok;
    if (mp_obj_is_str(data)) {
        size_t len;
        const char *s = mp_obj_str_get_data(data, &len);
        if (len >= QR_LEN) mp_raise_ValueError(MP_ERROR_TEXT("too long for a QR code"));
        memcpy(qr_out, s, len), qr_out[len] = 0;
        ok = qrcodegen_encodeText((const char *)qr_out, qr_temp, qr_out, qrcodegen_Ecc_LOW, qrcodegen_VERSION_MIN,
                                  QR_VERSION_MAX, qrcodegen_Mask_AUTO, false);
    } else {
        mp_buffer_info_t b;
        mp_get_buffer_raise(data, &b, MP_BUFFER_READ);
        if (b.len > QR_LEN) mp_raise_ValueError(MP_ERROR_TEXT("too long for a QR code"));
        memcpy(qr_temp, b.buf, b.len);
        ok = qrcodegen_encodeBinary(qr_temp, b.len, qr_out, qrcodegen_Ecc_LOW, qrcodegen_VERSION_MIN,
                                    QR_VERSION_MAX, qrcodegen_Mask_AUTO, false);
    }
    if (!ok) mp_raise_ValueError(MP_ERROR_TEXT("too long for a QR code"));
    int n = qrcodegen_getSize(qr_out);
    return mp_obj_new_bytes(qr_out, 1 + ((size_t)n * n + 7) / 8);
}
static MP_DEFINE_CONST_FUN_OBJ_1(gfx_qr_encode_obj, gfx_qr_encode);

/* A finder pattern, or for SeedQR's 25x25 and 29x29 the one alignment pattern: square in every style, as
 * qrcode's eye drawer and SeedSigner's patch over the alignment pattern have them */
static bool qr_square(int n, int r, int c) {
    if ((r < 7 && c < 7) || (r < 7 && c >= n - 7) || (r >= n - 7 && c < 7)) return true;
    return n > 21 && r >= n - 9 && r < n - 4 && c >= n - 9 && c < n - 4;
}

/* qr(code, border, x, y, w, h, fg, bg, style, cx0, cy0, cx1, cy1): qr_encode's code with `border` light
 * modules each side, stretched over w x h at (x, y); style 1 squares, 2 dots, 3 gapped squares */
static mp_obj_t gfx_qr(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    mp_buffer_info_t q;
    mp_get_buffer_raise(args[0], &q, MP_BUFFER_READ);
    const uint8_t *code = q.buf;
    int n = code[0], border = mp_obj_get_int(args[1]);
    if (q.len < 1 + ((size_t)n * n + 7) / 8) mp_raise_ValueError(MP_ERROR_TEXT("not a QR code"));
    int x = mp_obj_get_int(args[2]), y = mp_obj_get_int(args[3]);
    int w = mp_obj_get_int(args[4]), h = mp_obj_get_int(args[5]);
    uint8_t fg = mp_obj_get_int(args[6]), bg = mp_obj_get_int(args[7]);
    int style = mp_obj_get_int(args[8]);
    int cx0 = clampi(mp_obj_get_int(args[9]), 0, W), cy0 = CLIP_Y(args[10]);
    int cx1 = clampi(mp_obj_get_int(args[11]), 0, W), cy1 = CLIP_Y(args[12]);
    int N = n + 2 * border;
    if (w <= 0 || h <= 0) return mp_const_none;
    cx0 = x > cx0 ? x : cx0, cy0 = y > cy0 ? y : cy0;
    cx1 = x + w < cx1 ? x + w : cx1, cy1 = y + h < cy1 ? y + h : cy1;
    for (int py = cy0; py < cy1; py++) {
        /* Module of the pixel's centre, as PIL's nearest-neighbour resize of SeedSigner's picture picks it */
        int v = py - y, mr = (2 * v + 1) * N / (2 * h);
        int top = (2 * mr * h + N - 1) / (2 * N), cs_y = (2 * (mr + 1) * h + N - 1) / (2 * N) - top, fy = v - top;
        for (int px = cx0; px < cx1; px++) {
            int u = px - x, mc = (2 * u + 1) * N / (2 * w);
            int r = mr - border, c = mc - border;
            bool dark = qrcodegen_getModule(code, c, r);
            if (dark && style != 1 && !qr_square(n, r, c)) {
                int left = (2 * mc * w + N - 1) / (2 * N), cs_x = (2 * (mc + 1) * w + N - 1) / (2 * N) - left;
                int fx = u - left;
                if (style == 2) {
                    int ax = 2 * fx + 1 - cs_x, ay = 2 * fy + 1 - cs_y;
                    dark = ax * ax + ay * ay <= cs_x * cs_y;
                } else {
                    int dx = (cs_x + 5) / 10, dy = (cs_y + 5) / 10;
                    dark = fx >= dx && fx < cs_x - dx && fy >= dy && fy < cs_y - dy;
                }
            }
            *PX(px, py) = dark ? fg : bg;
        }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(gfx_qr_obj, 13, 13, gfx_qr);

/* colour(r, g, b): the palette index for that colour */
static mp_obj_t gfx_colour(mp_obj_t r, mp_obj_t g, mp_obj_t b) {
    return mp_obj_new_int(encode(mp_obj_get_int(r), mp_obj_get_int(g), mp_obj_get_int(b)));
}
static MP_DEFINE_CONST_FUN_OBJ_3(gfx_colour_obj, gfx_colour);


static const mp_rom_map_elem_t globals[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR__gfx) },
    { MP_ROM_QSTR(MP_QSTR_show), MP_ROM_PTR(&gfx_show_obj) },
    { MP_ROM_QSTR(MP_QSTR_fill), MP_ROM_PTR(&gfx_fill_obj) },
    { MP_ROM_QSTR(MP_QSTR_glyph), MP_ROM_PTR(&gfx_glyph_obj) },
    { MP_ROM_QSTR(MP_QSTR_blit), MP_ROM_PTR(&gfx_blit_obj) },
    { MP_ROM_QSTR(MP_QSTR_camera), MP_ROM_PTR(&gfx_camera_obj) },
    { MP_ROM_QSTR(MP_QSTR_band), MP_ROM_PTR(&gfx_band_obj) },
    { MP_ROM_QSTR(MP_QSTR_shape), MP_ROM_PTR(&gfx_shape_obj) },
    { MP_ROM_QSTR(MP_QSTR_glyphs), MP_ROM_PTR(&gfx_glyphs_obj) },
    { MP_ROM_QSTR(MP_QSTR_shade), MP_ROM_PTR(&gfx_shade_obj) },
    { MP_ROM_QSTR(MP_QSTR_colour), MP_ROM_PTR(&gfx_colour_obj) },
    { MP_ROM_QSTR(MP_QSTR_save), MP_ROM_PTR(&gfx_save_obj) },
    { MP_ROM_QSTR(MP_QSTR_qr_encode), MP_ROM_PTR(&gfx_qr_encode_obj) },
    { MP_ROM_QSTR(MP_QSTR_qr), MP_ROM_PTR(&gfx_qr_obj) },
    { MP_ROM_QSTR(MP_QSTR_WIDTH), MP_ROM_INT(W) },
    { MP_ROM_QSTR(MP_QSTR_HEIGHT), MP_ROM_INT(H) },
    { MP_ROM_QSTR(MP_QSTR_BAND), MP_ROM_INT(BAND) },
};
static MP_DEFINE_CONST_DICT(globals_dict, globals);

const mp_obj_module_t gfx_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&globals_dict,
};
MP_REGISTER_MODULE(MP_QSTR__gfx, gfx_module);
