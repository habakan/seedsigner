/* signer.wasm's exports, linked natively, for MicroPython: the Pico cannot afford to interpret them
 * (docs/pico.md). Each is a function of the same name; a pointer comes back as an offset into
 * memory(), as a wasm host reads linear memory. Generated from bitwasm-signer's wasm_main.c */
#include <stdint.h>
#include "py/obj.h"
#include "py/objarray.h"
#include "py/runtime.h"

const void * signer_input(void);
unsigned int signer_input_cap(void);
const void * signer_plan(void);
const void * signer_prevtx(void);
const void * signer_review_output(void);
const void * signer_display_output(void);
const void * signer_facts_output(void);
const void * signer_nonces(void);
const void * signer_nonce_points(void);
const void * signer_sigs(void);
const void * signer_xpub_output(void);
const void * signer_desc_output(void);
const void * signer_address_output(void);
const void * signer_mnemonic_output(void);
const void * signer_seedqr_output(void);
const void * signer_message_output(void);
const void * signer_message_sig(void);
const void * signer_multisig_output(void);
const void * signer_cbor_output(void);
const void * signer_words_output(void);
const void * signer_wordlist(void);
int signer_init(unsigned int);
int signer_seed_from_mnemonic(unsigned int, unsigned int);
int signer_seed_from_seedqr(unsigned int, unsigned int);
int signer_load_seed(void);
void signer_unload(void);
unsigned int signer_fingerprint(void);
int signer_set_prevtx(unsigned int, unsigned int, unsigned int);
int signer_review(void);
int signer_display(void);
int signer_facts(void);
int signer_sign(void);
int signer_xpub(unsigned int, unsigned int);
int signer_address(unsigned int, unsigned int, unsigned int, unsigned int);
int signer_find_address(unsigned int, unsigned int, unsigned int);
int signer_mnemonic_from_entropy(unsigned int);
int signer_mnemonic_from_dice(unsigned int, unsigned int);
int signer_dice_check(unsigned int, unsigned int);
int signer_seedqr_from_mnemonic(unsigned int, unsigned int);
int signer_bip85_mnemonic(unsigned int, unsigned int);
int signer_message_review(unsigned int, unsigned int, unsigned int, unsigned int, unsigned int);
int signer_message_sign(void);
int signer_multisig_load(unsigned int);
int signer_multisig_load_cbor(unsigned int);
int signer_multisig_watch(unsigned int);
void signer_multisig_unload(void);
int signer_multisig_address(unsigned int, unsigned int);
int signer_multisig_find_address(unsigned int, unsigned int);
int signer_account_cbor(unsigned int);
int signer_multisig_cbor(void);
unsigned int signer_word_letters(unsigned int, unsigned int);
int signer_word_matches(unsigned int, unsigned int);
int signer_final_words(unsigned int);

static uintptr_t base;

static mp_obj_t offset(const void *p) {
    return mp_obj_new_int_from_uint((uintptr_t)p - base);
}

static mp_obj_t w_signer_input(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_input());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_input_obj, 0, 0, w_signer_input);

static mp_obj_t w_signer_input_cap(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int_from_uint(signer_input_cap());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_input_cap_obj, 0, 0, w_signer_input_cap);

static mp_obj_t w_signer_plan(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_plan());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_plan_obj, 0, 0, w_signer_plan);

static mp_obj_t w_signer_prevtx(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_prevtx());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_prevtx_obj, 0, 0, w_signer_prevtx);

static mp_obj_t w_signer_review_output(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_review_output());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_review_output_obj, 0, 0, w_signer_review_output);

static mp_obj_t w_signer_display_output(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_display_output());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_display_output_obj, 0, 0, w_signer_display_output);

static mp_obj_t w_signer_facts_output(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_facts_output());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_facts_output_obj, 0, 0, w_signer_facts_output);

static mp_obj_t w_signer_nonces(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_nonces());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_nonces_obj, 0, 0, w_signer_nonces);

static mp_obj_t w_signer_nonce_points(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_nonce_points());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_nonce_points_obj, 0, 0, w_signer_nonce_points);

static mp_obj_t w_signer_sigs(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_sigs());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_sigs_obj, 0, 0, w_signer_sigs);

static mp_obj_t w_signer_xpub_output(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_xpub_output());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_xpub_output_obj, 0, 0, w_signer_xpub_output);

static mp_obj_t w_signer_desc_output(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_desc_output());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_desc_output_obj, 0, 0, w_signer_desc_output);

static mp_obj_t w_signer_address_output(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_address_output());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_address_output_obj, 0, 0, w_signer_address_output);

static mp_obj_t w_signer_mnemonic_output(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_mnemonic_output());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_mnemonic_output_obj, 0, 0, w_signer_mnemonic_output);

static mp_obj_t w_signer_seedqr_output(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_seedqr_output());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_seedqr_output_obj, 0, 0, w_signer_seedqr_output);

static mp_obj_t w_signer_message_output(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_message_output());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_message_output_obj, 0, 0, w_signer_message_output);

static mp_obj_t w_signer_message_sig(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_message_sig());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_message_sig_obj, 0, 0, w_signer_message_sig);

static mp_obj_t w_signer_multisig_output(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_multisig_output());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_multisig_output_obj, 0, 0, w_signer_multisig_output);

static mp_obj_t w_signer_cbor_output(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_cbor_output());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_cbor_output_obj, 0, 0, w_signer_cbor_output);

static mp_obj_t w_signer_words_output(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_words_output());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_words_output_obj, 0, 0, w_signer_words_output);

static mp_obj_t w_signer_wordlist(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return offset(signer_wordlist());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_wordlist_obj, 0, 0, w_signer_wordlist);

static mp_obj_t w_signer_init(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_init((unsigned int)mp_obj_get_int_truncated(a[0])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_init_obj, 1, 1, w_signer_init);

static mp_obj_t w_signer_seed_from_mnemonic(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_seed_from_mnemonic((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_seed_from_mnemonic_obj, 2, 2, w_signer_seed_from_mnemonic);

static mp_obj_t w_signer_seed_from_seedqr(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_seed_from_seedqr((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_seed_from_seedqr_obj, 2, 2, w_signer_seed_from_seedqr);

static mp_obj_t w_signer_load_seed(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_load_seed());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_load_seed_obj, 0, 0, w_signer_load_seed);

static mp_obj_t w_signer_unload(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    signer_unload();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_unload_obj, 0, 0, w_signer_unload);

static mp_obj_t w_signer_fingerprint(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int_from_uint(signer_fingerprint());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_fingerprint_obj, 0, 0, w_signer_fingerprint);

static mp_obj_t w_signer_set_prevtx(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_set_prevtx((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1]), (unsigned int)mp_obj_get_int_truncated(a[2])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_set_prevtx_obj, 3, 3, w_signer_set_prevtx);

static mp_obj_t w_signer_review(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_review());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_review_obj, 0, 0, w_signer_review);

static mp_obj_t w_signer_display(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_display());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_display_obj, 0, 0, w_signer_display);

static mp_obj_t w_signer_facts(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_facts());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_facts_obj, 0, 0, w_signer_facts);

static mp_obj_t w_signer_sign(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_sign());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_sign_obj, 0, 0, w_signer_sign);

static mp_obj_t w_signer_xpub(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_xpub((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_xpub_obj, 2, 2, w_signer_xpub);

static mp_obj_t w_signer_address(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_address((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1]), (unsigned int)mp_obj_get_int_truncated(a[2]), (unsigned int)mp_obj_get_int_truncated(a[3])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_address_obj, 4, 4, w_signer_address);

static mp_obj_t w_signer_find_address(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_find_address((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1]), (unsigned int)mp_obj_get_int_truncated(a[2])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_find_address_obj, 3, 3, w_signer_find_address);

static mp_obj_t w_signer_mnemonic_from_entropy(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_mnemonic_from_entropy((unsigned int)mp_obj_get_int_truncated(a[0])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_mnemonic_from_entropy_obj, 1, 1, w_signer_mnemonic_from_entropy);

static mp_obj_t w_signer_mnemonic_from_dice(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_mnemonic_from_dice((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_mnemonic_from_dice_obj, 2, 2, w_signer_mnemonic_from_dice);

static mp_obj_t w_signer_dice_check(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_dice_check((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_dice_check_obj, 2, 2, w_signer_dice_check);

static mp_obj_t w_signer_seedqr_from_mnemonic(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_seedqr_from_mnemonic((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_seedqr_from_mnemonic_obj, 2, 2, w_signer_seedqr_from_mnemonic);

static mp_obj_t w_signer_bip85_mnemonic(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_bip85_mnemonic((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_bip85_mnemonic_obj, 2, 2, w_signer_bip85_mnemonic);

static mp_obj_t w_signer_message_review(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_message_review((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1]), (unsigned int)mp_obj_get_int_truncated(a[2]), (unsigned int)mp_obj_get_int_truncated(a[3]), (unsigned int)mp_obj_get_int_truncated(a[4])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_message_review_obj, 5, 5, w_signer_message_review);

static mp_obj_t w_signer_message_sign(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_message_sign());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_message_sign_obj, 0, 0, w_signer_message_sign);

static mp_obj_t w_signer_multisig_load(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_multisig_load((unsigned int)mp_obj_get_int_truncated(a[0])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_multisig_load_obj, 1, 1, w_signer_multisig_load);

static mp_obj_t w_signer_multisig_load_cbor(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_multisig_load_cbor((unsigned int)mp_obj_get_int_truncated(a[0])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_multisig_load_cbor_obj, 1, 1, w_signer_multisig_load_cbor);

static mp_obj_t w_signer_multisig_watch(size_t n, const mp_obj_t *a) {
    (void)n;
    return mp_obj_new_int(signer_multisig_watch((unsigned int)mp_obj_get_int_truncated(a[0])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_multisig_watch_obj, 1, 1, w_signer_multisig_watch);

static mp_obj_t w_signer_multisig_unload(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    signer_multisig_unload();
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_multisig_unload_obj, 0, 0, w_signer_multisig_unload);

static mp_obj_t w_signer_multisig_address(size_t n, const mp_obj_t *a) {
    (void)n;
    return mp_obj_new_int(signer_multisig_address((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_multisig_address_obj, 2, 2, w_signer_multisig_address);

static mp_obj_t w_signer_multisig_find_address(size_t n, const mp_obj_t *a) {
    (void)n;
    return mp_obj_new_int(signer_multisig_find_address((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_multisig_find_address_obj, 2, 2, w_signer_multisig_find_address);

static mp_obj_t w_signer_account_cbor(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_account_cbor((unsigned int)mp_obj_get_int_truncated(a[0])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_account_cbor_obj, 1, 1, w_signer_account_cbor);

static mp_obj_t w_signer_multisig_cbor(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_multisig_cbor());
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_multisig_cbor_obj, 0, 0, w_signer_multisig_cbor);

static mp_obj_t w_signer_word_letters(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int_from_uint(signer_word_letters((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_word_letters_obj, 2, 2, w_signer_word_letters);

static mp_obj_t w_signer_word_matches(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_word_matches((unsigned int)mp_obj_get_int_truncated(a[0]), (unsigned int)mp_obj_get_int_truncated(a[1])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_word_matches_obj, 2, 2, w_signer_word_matches);

static mp_obj_t w_signer_final_words(size_t n, const mp_obj_t *a) {
    (void)n, (void)a;
    return mp_obj_new_int(signer_final_words((unsigned int)mp_obj_get_int_truncated(a[0])));
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(w_signer_final_words_obj, 1, 1, w_signer_final_words);

/* Every buffer, from the lowest to the highest plus the largest one's size: the wordlist may sit in
 * flash, the rest in RAM, so on the Pico this view spans both and only its buffers are touched */
static mp_obj_t memory(void) {
    const void *p[] = {signer_input(), signer_plan(), signer_prevtx(), signer_review_output(), signer_display_output(), signer_facts_output(), signer_nonces(), signer_nonce_points(), signer_sigs(), signer_xpub_output(), signer_desc_output(), signer_address_output(), signer_mnemonic_output(), signer_seedqr_output(), signer_message_output(), signer_message_sig(), signer_multisig_output(), signer_cbor_output(), signer_words_output(), signer_wordlist()};
    uintptr_t lo = UINTPTR_MAX, hi = 0;
    for (size_t i = 0; i < MP_ARRAY_SIZE(p); i++) {
        lo = (uintptr_t)p[i] < lo ? (uintptr_t)p[i] : lo;
        hi = (uintptr_t)p[i] > hi ? (uintptr_t)p[i] : hi;
    }
    base = lo;
    return mp_obj_new_bytearray_by_ref(hi - lo + 32768, (void *)lo);
}
static MP_DEFINE_CONST_FUN_OBJ_0(memory_obj, memory);

static const mp_rom_map_elem_t globals[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR__bitwasm) },
    { MP_ROM_QSTR(MP_QSTR_memory), MP_ROM_PTR(&memory_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_input), MP_ROM_PTR(&w_signer_input_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_input_cap), MP_ROM_PTR(&w_signer_input_cap_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_plan), MP_ROM_PTR(&w_signer_plan_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_prevtx), MP_ROM_PTR(&w_signer_prevtx_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_review_output), MP_ROM_PTR(&w_signer_review_output_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_display_output), MP_ROM_PTR(&w_signer_display_output_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_facts_output), MP_ROM_PTR(&w_signer_facts_output_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_nonces), MP_ROM_PTR(&w_signer_nonces_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_nonce_points), MP_ROM_PTR(&w_signer_nonce_points_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_sigs), MP_ROM_PTR(&w_signer_sigs_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_xpub_output), MP_ROM_PTR(&w_signer_xpub_output_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_desc_output), MP_ROM_PTR(&w_signer_desc_output_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_address_output), MP_ROM_PTR(&w_signer_address_output_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_mnemonic_output), MP_ROM_PTR(&w_signer_mnemonic_output_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_seedqr_output), MP_ROM_PTR(&w_signer_seedqr_output_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_message_output), MP_ROM_PTR(&w_signer_message_output_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_message_sig), MP_ROM_PTR(&w_signer_message_sig_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_multisig_output), MP_ROM_PTR(&w_signer_multisig_output_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_cbor_output), MP_ROM_PTR(&w_signer_cbor_output_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_words_output), MP_ROM_PTR(&w_signer_words_output_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_wordlist), MP_ROM_PTR(&w_signer_wordlist_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_init), MP_ROM_PTR(&w_signer_init_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_seed_from_mnemonic), MP_ROM_PTR(&w_signer_seed_from_mnemonic_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_seed_from_seedqr), MP_ROM_PTR(&w_signer_seed_from_seedqr_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_load_seed), MP_ROM_PTR(&w_signer_load_seed_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_unload), MP_ROM_PTR(&w_signer_unload_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_fingerprint), MP_ROM_PTR(&w_signer_fingerprint_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_set_prevtx), MP_ROM_PTR(&w_signer_set_prevtx_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_review), MP_ROM_PTR(&w_signer_review_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_display), MP_ROM_PTR(&w_signer_display_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_facts), MP_ROM_PTR(&w_signer_facts_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_sign), MP_ROM_PTR(&w_signer_sign_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_xpub), MP_ROM_PTR(&w_signer_xpub_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_address), MP_ROM_PTR(&w_signer_address_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_find_address), MP_ROM_PTR(&w_signer_find_address_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_mnemonic_from_entropy), MP_ROM_PTR(&w_signer_mnemonic_from_entropy_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_mnemonic_from_dice), MP_ROM_PTR(&w_signer_mnemonic_from_dice_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_dice_check), MP_ROM_PTR(&w_signer_dice_check_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_seedqr_from_mnemonic), MP_ROM_PTR(&w_signer_seedqr_from_mnemonic_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_bip85_mnemonic), MP_ROM_PTR(&w_signer_bip85_mnemonic_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_message_review), MP_ROM_PTR(&w_signer_message_review_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_message_sign), MP_ROM_PTR(&w_signer_message_sign_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_multisig_load), MP_ROM_PTR(&w_signer_multisig_load_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_multisig_load_cbor), MP_ROM_PTR(&w_signer_multisig_load_cbor_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_multisig_unload), MP_ROM_PTR(&w_signer_multisig_unload_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_multisig_watch), MP_ROM_PTR(&w_signer_multisig_watch_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_multisig_address), MP_ROM_PTR(&w_signer_multisig_address_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_multisig_find_address), MP_ROM_PTR(&w_signer_multisig_find_address_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_account_cbor), MP_ROM_PTR(&w_signer_account_cbor_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_multisig_cbor), MP_ROM_PTR(&w_signer_multisig_cbor_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_word_letters), MP_ROM_PTR(&w_signer_word_letters_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_word_matches), MP_ROM_PTR(&w_signer_word_matches_obj) },
    { MP_ROM_QSTR(MP_QSTR_signer_final_words), MP_ROM_PTR(&w_signer_final_words_obj) },
};
static MP_DEFINE_CONST_DICT(globals_dict, globals);

const mp_obj_module_t bitwasm_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&globals_dict,
};
MP_REGISTER_MODULE(MP_QSTR__bitwasm, bitwasm_module);
