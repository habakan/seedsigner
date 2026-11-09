# SeedSigner on the Raspberry Pi Pico 2

The goal is SeedSigner's own Python (`controller`, `views`, `models`) running on an RP2350 under
MicroPython, with every key operation in bitwasm-signer's `signer.wasm` and every PSBT parse in
`parser.wasm`, both on WAMR. The display is the same 240x240 ST7789 that SeedSigner already uses.

## Why it can work

- `signer.wasm` already covers what embit does for SeedSigner: BIP39 seeds, SeedQR, new mnemonics from
  entropy or dice, BIP85, xpubs and descriptors, address lookup, message signing, multisig registration
  and PSBT review and signing. `parser.wasm` parses PSBTs and assembles UR.
- The Python side talks to WAMR through one small class, `bitwasm_signer.wamr.Instance`. The browser
  simulator already swaps it for the browser's WebAssembly; on the Pico it becomes a MicroPython C module.
- MicroPython has no `sha512`, `pbkdf2_hmac` or secp256k1, so embit cannot come along without C modules
  for them, and with them it runs out of heap on a two-input PSBT ("Why not embit" below).

## Stages

Each stage ends with a measurement that decides whether the next one is worth doing.

1. **No embit, on CPython.** `src/seedsigner` imports nothing from embit; the existing tests pass
   against the wasm modules. Gate: the test suite, plus an import check with `embit` blocked.
2. **Heap on MicroPython's Unix port.** Run the controller with stub display and camera and measure the
   peak GC heap. Gate: it fits beside two wasm instances in 520KB, or we decide on PSRAM.
3. **RP2350 firmware.** MicroPython with C modules for WAMR, the display, the camera, the Rust QR
   reader and the buttons; SeedSigner frozen into Flash.
4. **On hardware.** Load a seed, review and sign a PSBT on signet.

## Measured on the Pico 2

`signer.wasm` (bitwasm-signer d4b970a) on WAMR 2.4.5's classic interpreter, RP2350 RISC-V at 150MHz,
BIP39's test seed, testnet. `tools/pico/signer_bench` builds it against bitwasm-signer-pico's SDK and
WAMR; results are read from RAM over SWD.

| | |
|---|---:|
| load / instantiate | 0.11 s / 0.001 s |
| seed from mnemonic (PBKDF2) | **21.9 s** (native, in bitwasm-signer-pico: 0.47 s) |
| account xpub | 1.4 s |
| one address, P2WPKH / P2TR | 2.1 s / 3.7 s |
| `find_address`, 2 x 20 children | 30.2 s |
| RAM: WAMR pool peak + writable module copy | 148 KB + 102 KB |

Interpreted, the signer is too slow to use (an address page of ten takes 21 s) and its 250 KB leaves
too little for MicroPython beside `parser.wasm`. bitwasm-signer-pico reached the same conclusion and
runs the signer's C natively, keeping only the parser, which reads untrusted input, in WAMR. The Pico
build will do the same: the same C as `signer.wasm`, linked natively behind the same `signer_*`
functions, so the Python side does not change.

## SeedSigner's Python on the Pico 2

MicroPython 1.29.0 (RPI_PICO2, RISC-V) with the signer linked natively (`pico/modules/bitwasm`), and
SeedSigner's own `models/seed.py`, `helpers/wallet.py` and `helpers/mnemonic_generation.py` run as they
are. `pico/tests/smoke.py` prints the same lines on the device as on CPython: fingerprint, SLIP-132 xpubs,
mainnet and regtest addresses, a BIP137 message signature, a BIP85 child, dice and checksum words.

| `pico/tests/bench.py`, modules mounted over USB as .mpy | |
|---|---:|
| seed from mnemonic (PBKDF2) | 0.55 s |
| account xpub / one address / ten addresses | 65 ms / 27 ms / 271 ms |
| BIP137 message signature | 81 ms |
| heap after importing and using them | 67 KB, 321 KB free |

Frozen into the firmware (`pico/manifest.py`), the device boots on its own: a one-line `main.py`
runs `selftest`, which loads BIP39's test seed, checks its fingerprint and two addresses, and reviews
and signs bitwasm-signer's `own_mixed_nwu` PSBT through SeedSigner's `BitwasmReview`: `parser.wasm` on
WAMR (`pico/modules/wamr`), then the native signer. The signed PSBT is the bytes CPython's SeedSigner
produces. At boot the imports take 63 ms, the seed 0.55 s, the PSBT 0.60 s, and 197 KB of heap is left.
WAMR's 160 KB pool peaks at 157 KB on that PSBT, so larger ones or UR assembly may need more.

```sh
git submodule update --init pico/third_party/micropython-pil   # the PIL and _gfx, once
make -C pico rp2 BITWASM_SIGNER=<bitwasm-signer> PICO_TOOLCHAIN_PATH=<RISC-V GCC>   # then flash firmware.elf
make -C pico device-install PORT=/dev/cu.usbmodem...    # main.py, once
make -C pico mpy && make -C pico device-smoke PORT=...  # or run a script with the modules mounted
```

## PSBTs without embit

`models/psbt_wasm.py`'s `WasmPSBTParser` gives the PSBT views what embit's `PSBTParser` does, from
`parser.wasm`'s plan and the signer's review alone; `models/psbt.py` picks it where embit is missing.
`tests/conftest.py` repeats every successful embit parse in the suite with it and compares what the views
read: 137 parses agree. `tests/test_flows_psbt_wasm.py` scans, reviews and signs through the views with
both parsers, and `pico/tests/psbt.py` prints the same review and signed PSBT on the Pico 2 as on CPython.

When the signer refuses a PSBT, the views show the upstream error for it: a missing or tampered input UTXO,
a negative fee, an input this seed does not own, or a malformed OP_RETURN (the signer is started with its
strict OP_RETURN option, matching upstream's rules). 20 upstream tests expect what the signer does not do
and are marked xfail in `tests/conftest.py`, each with its reason.

Two differences, both from the signer checking each output itself:

- P2WSH change claimed with this seed's fingerprint is shown as change, but signing is refused until a
  multisig descriptor proves it ("Verify multisig change"). The plan does not carry the output's witness
  script, so it cannot be checked from the PSBT alone (3 of the 137 parses).
- Inputs of mixed script types are accepted; embit's parser refuses them as "Mixed inputs".

## Multisig without embit

`helpers/wallet.py`'s `Multisig` takes a `wsh(sortedmulti(...))` descriptor of up to three keys, normalized
to `/<0;1>/*`. With a loaded seed among the cosigners it is registered with the signer, which then proves
change outputs and signs. With no such seed it is only watched: addresses, but no review. The address
explorer and address verification use it either way, as upstream does from a descriptor alone.

| On the Pico 2, a 2-of-3 | with a seed | watched |
|---|---:|---:|
| explorer page of ten addresses | 1.0 s | 1.0 s |
| verify receive #3 / change #1 | 0.9 s / 0.7 s | 1.2 s / 0.6 s |

The signed PSBT is what `parser_finalize_trimmed` writes: the unsigned transaction and the signatures, as
`PSBTParser.trim` leaves it, without embit. Previous transactions would otherwise make it tens of KB.

## Why not embit

Tried on the device on 2026-11-09, to see whether bitwasm-signer is needed at all once the heap had grown:
embit frozen into the firmware, its hashing and secp256k1 as C modules (kdmukai's `_hashlib_ext` and
secp256k1 bindings, over bitwasm-signer's C, since MicroPython has neither), WAMR left out, and upstream's
`PSBTParser` and `sign_with` patched into SeedSigner's views for the test (not in this repository). The same
two-input P2WPKH PSBT went through the same screens on both builds, with no screenshots taken:

| screen | bitwasm-signer: free / largest hole | embit: free / largest hole |
|---|---:|---:|
| scan | 94.2 KB / 3.3 KB | 68.0 KB / 2.6 KB |
| seed chosen | 75.1 KB / 2.9 KB | 52.9 KB / 1.1 KB |
| PSBT overview | 65.8 KB / 2.2 KB | 45.4 KB / 1.4 KB |
| PSBT math | 64.3 KB / 1.1 KB | 40.7 KB / 0.4-0.5 KB, then MemoryError |
| signed QR | 72.6 KB / 2.4 KB | not reached |

The embit build stopped at the math screen both times it was run, on 160 to 300-byte allocations for the
screen's own parts and fonts. Three things add up:

- **Code that stays loaded.** embit's modules and upstream's parser take 26 KB of heap before any PSBT is
  read: module dictionaries, classes and functions, held for as long as the app runs.
- **A PSBT as objects.** embit parses a PSBT into a tree of objects, one for each input, output, key,
  derivation path, script and amount, each with its own dictionary. MicroPython allocates in 16-byte blocks,
  so the tree is several times the PSBT's size: 17 KB for two inputs and 62 KB for ten, measured on their
  own, against a 0.8 KB and a 3.5 KB PSBT. The views keep it alive through the whole review.
- **Holes that never join.** MicroPython's garbage collector does not move live objects. Thousands of small
  ones scattered through the heap leave 40 KB free in pieces too small for a 300-byte allocation.

None of this is a leak; the objects are in use. bitwasm-signer avoids all three:

- **The PSBT stays bytes.** The UR decoder keeps the scanned fragments as they arrived (2 KB pieces, or the
  signer's prevtx buffer for a large PSBT), and `parser.wasm` reads them in place. Nothing becomes a Python
  object per input or output.
- **Parsing happens outside the heap.** `parser.wasm` runs on WAMR in a fixed 110 KB pool beside the heap
  (lent to the camera and QR reader while scanning), and writes its plan straight into the native signer's
  buffer (`_bitwasm.plan_buffer()`). Its working memory is that pool, reused by the next parse, so it
  never fragments the heap.
- **Signing is native C.** Keys and signatures stay in one C module; Python receives the signed PSBT,
  already trimmed for the QR.

So the views hold a few small Python values per screen, and the same flow signs PSBTs up to 25 KB, ten
inputs and 200 outputs, with 53 to 72 KB free through the review. It is also faster: on a Cortex-M4,
Embench kernels ran about 15 times faster as WebAssembly on wasm3 or WAMR than as Python on MicroPython
(Moron and Wallentowitz, [Benchmarking WebAssembly for Embedded Systems](https://doi.org/10.1145/3736169),
2025). The parse being the one input an attacker controls, running it in a sandbox is the other reason.

### With a larger heap and MicroPython's own advice

MicroPython's guide to constrained devices ([The heap, Fragmentation](https://docs.micropython.org/en/latest/reference/constrained.html#fragmentation))
says to allocate large buffers early and not to create and drop many small objects. Tried on the same
device, with the scanned PSBT held in the GC heap as an embit port would hold it:

- **A larger heap.** The embit build still carried bitwasm-signer's PSBT buffers (32 KB of prevtx, 13 KB of
  plan and more) for its hashing and secp256k1. Shrinking them took the GC heap from 265 to 324 KB.
- **`compress`.** embit's `PSBT.read_from(stream, compress=CompressMode.CLEAR_ALL)` streams each previous
  transaction past and keeps only the spent output and the transaction's hash, where upstream reads them
  into objects. The checks upstream makes on `non_witness_utxo` were made on what embit kept: the txid, and
  that `witness_utxo` agrees. The signed PSBTs were upstream's bytes.
- **The UR decoder's word table early.** Bytewords builds a 2.7 KB table at the first scanned part. On the
  265 KB heap no hole was that large, and upstream's `URDecoder` drops a part on any exception, so the scan
  sat on the camera screen without advancing. Building it at boot fixed that (this fork now does so too).

| | 2 inputs | 10 inputs | 25 KB, 10 in and 200 out |
|---|---|---|---|
| embit, 265 KB, all three but the heap | MemoryError in the parse | MemoryError in the parse | |
| embit, 324 KB, all three | signs | signs; 2.4 KB the largest hole | signs; a MemoryError drawing the QR screen's tip |
| bitwasm-signer, 249 KB | signs | signs | signs; 53 to 72 KB free |

So embit can sign a 25 KB PSBT on the RP2350, given 75 KB more heap than bitwasm-signer's build, a streamed
parse, and buffers taken early, and then with 1 to 2 KB holes between it and a MemoryError. The techniques
move the limit; a PSBT held as objects still grows with its inputs, and the parser's code still stays
loaded. bitwasm-signer is that advice taken to its end: nothing per input in the heap, and the parse's
working memory a buffer taken at boot.

## Reading QR codes

`models/decode_qr.py` runs on the device for everything but the camera image (pyzbar, still the Pi's).
`SEEDSIGNER_RECORD_QR=<file> pytest` writes every DecodeQR session in the suite, 184 of them, and
`pico/tests/qr_replay.py` decodes them again: the Pico 2 prints what MicroPython's unix port does, and
both print what CPython does except one generic wallet descriptor, which needs embit to validate.

What MicroPython needed:

- `helpers/qr_text.py` for decode_qr's regular expressions, since MicroPython's `re` has no flags and no
  `{m,n}`; `tests/test_qr_text.py` checks each against `re` on generated strings.
- Double floats in the firmware (`pico/modules/micropython.cmake`). BC-UR picks mixed fragments with a
  double-precision sampler, so single precision cannot decode a UR that needs them.
- Fewer large allocations late. The heap fragments as UR frames arrive: after 29 frames 88 KB is used and
  the largest free block is under 9 KB. The fountain decoder now takes the message's room with the
  first frame and fills it in place, and UR's CRC-32 is binascii's, not a table walked with integers
  that are heap objects past 2**30 on a 32-bit MicroPython.
- No list of 2048 four-letter prefixes per QR (`qr_text.four_letter_word`), `UnicodeError` for
  `UnicodeDecodeError`, `zlib.decompress` for `decompressobj`, and a `logging` that takes `exc_info`.

Fragmentation is the device's open risk: a 32 KB PSBT will want its buffer taken early, as the UR
message's now is.

## The camera

`pico/modules/camera` is bitwasm-signer-pico's DVP camera driver (OV7670/OV7675) and its Rust QR reader
as `_camera`. The 320x240 frame and the reader's state, about 80 KB, are borrowed from WAMR's pool: the
RAM cannot hold them beside it, and parser.wasm is not needed while a code is being scanned. Borrowing
ends the parser's instance; `helpers/bitwasm.py` starts a new one on the next PSBT.

`pico/tests/scan.py` feeds frames to SeedSigner's `DecodeQR` and, for a PSBT, reviews and signs it.
Pointed at a laptop screen cycling bitwasm-signer's `own_p2wpkh_2in_nwu` as 21 UR frames (v5, 0.4 s
each), it completed in 42 s, reading 40 of 108 frames (0.39 s a frame), and signed it into the bytes
CPython does. Synthetic frames read in 0.33 s (SeedQR) and 0.44 s (UR, v11).

Through SeedSigner's own scan screen, with the camera preview drawn between reads, the same 21-frame UR
took 15 s and 33 s from pressing Scan to the signer selection; how long depends on which fountain parts
are caught.

## The screen

SeedSigner's own screens draw on the Pico's ST7789 through a PIL of the Pico's, now its own repository
([micropython-pil](https://github.com/habakan/micropython-pil), a submodule at `pico/third_party/micropython-pil`):

- The canvas is `_gfx`'s 240x240 framebuffer, one byte a pixel (a 6x6x6 colour cube and 40 greys, since
  SeedSigner's palette is greys), outside MicroPython's heap. Every other image is a list of drawing
  operations, replayed when pasted, so a text area or a button costs no pixel buffer.
- Fonts are bitmaps made at build time (`pico/tools/make_fonts.py`) for the fonts, sizes and characters
  rendering every screen uses (`pico/tools/record_fonts.py`, `pico/fonts_used.json`), 608 KB frozen. Their
  getbbox matches PIL's on all 5904 calls checked (`pico/tests/check_fonts.py`), so layouts come out the
  same: the main menu differs from PIL's only at antialiased edges (`pico/tests/render_screen.py`).
- The firmware takes 3 MB of the flash for this, leaving 1 MB of filesystem.
- `RPi.GPIO` is a shim mapping the Pi's header pins to bitwasm-signer-pico's joystick and keys, so
  `hardware/buttons.py` runs unchanged; the current two buttons are its down and press.

`pico/tests/screen.py` draws the main menu on the device in 0.47 s, leaving 106 KB of heap.

Besides English, the UI comes in the 15 upstream languages whose script OpenSans covers (`LOCALES` in
pico/Makefile: Latin, Cyrillic and Greek). `pico/tools/make_l10n.py` freezes their .mo catalogs, which
`pico/lib/gettext.py` searches in place in flash, and the fonts are recorded rendering every screen in each
of them: all 14305 getbbox calls match PIL's. They add about 540 KB of flash, and the language menu lists
them in upstream's order. Chinese, Japanese and Korean bring a Noto font of 0.6 to 0.7 MB each, so each goes
in on its own build (`make rp2 LOCALES=ja`, `ko` or `zh_Hans_CN`; 2.40 to 2.50 MB of firmware). Their glyphs
match PIL's on all 9724 to 10647 getbbox calls, and on the device Japanese draws as fast as English with
116 KB of heap free. Hindi, Thai, Persian and Arabic also need shaping, which MicroPython lacks.

QR codes (`pico/lib/seedsigner/helpers/qr.py`) are encoded by qrcodegen in `_gfx` (level L, smallest
version, no ECC boost, as qrcode and qrencode make them) and drawn straight onto the canvas when pasted, in
SeedSigner's three styles, with finder patterns and SeedQR's alignment pattern square. Through the shim on
CPython every style reads back with zbarimg, and with the same matrix differs from SeedSigner's picture
only at resampled edges (`pico/tests/check_qr.py`); qrcode scores masks its own way, so some codes (a
CompactSeedQR among them) get another, equally valid mask. On the device a SeedQR shows in 88 ms and an
animated UR PSBT frame in 118-148 ms (`pico/tests/qr_show.py`), plus the screen's own 167 ms hold.

`main.py` (`make device-install`) runs `Controller.start()` itself: the splash screen, then the main menu
driven by the buttons. Getting there took:

- Images (`resources/img`) converted to palette indices at build time (micropython-pil's `tools/make_images.py`).
- A copy of the canvas, as a toast takes, run-length encoded by `_gfx.save` rather than a 57.6 KB buffer.
- Version information from git at build time (`pico_version.py`), as SeedSigner OS has its version.json.
- `sys.exc_info` is missing on the rp2 port, so `to_micropython.py` hands `traceback.print_exc` and
  `format_exc` the exception (`--cpython` skips that, to run the tests on the transformed tree: all pass).
- A 16 KB stack for threads, which the preload thread's imports need.

## The whole flow on the device

SeedSigner's own screens now take a 12-word seed from the buttons, scan an animated UR PSBT with the
camera, review it, sign it and show the signed QR (driven over USB serial with `pico/tests/drive.py`).
RAM decided most of the way there:

| | KB |
|---|---|
| GC heap at first (WAMR's pool 160, a 57.6 KB canvas) | 168 |
| screens drawn a 40-row band at a time, no canvas | 223 |
| parser.wasm built without its UR decoder (bitwasm-signer), pool 116 KB | 275 |
| its stack 4 KB (1.7 KB used at most), pool 104 KB; C stack 20 KB, core1's 16 KB | 262 |

Now the GC heap is 249 KB: plan version 4 (520-byte witness scripts) grew the signer's static RAM and
WAMR's pool went to 110 KB, 16 KB in all, and libc moved to flash gave 14 KB back. 85 KB of it is free on
the main menu and 53 to 72 KB from the PSBT overview to the signed QR (`psbt_flow.py`'s twelve PSBTs). The firmware, SeedSigner and 15 languages frozen in, is
2.29 MB of its 3 MB of flash; 1 MB is left for the filesystem.

- The canvas is a list of drawing operations; an opaque one drops what it hides, or a keyboard's redraws
  pile up. A View's finished Screen is let go, or the back stack holds one per seed word.
- Buffers the heap may not find late are static or taken at import: WAMR's module copy. parser.wasm writes
  the plan straight into the native signer's (`_bitwasm.plan_buffer()`), with no copy in the heap.
- MicroPython is patched (`pico/patches/micropython-rp2.patch`): a GIL, as SeedSigner's threads assume
  CPython's; one static 16 KB core1 stack, as a heap one cannot be found and its MemoryError left core1
  claimed; a 20 KB C stack, as the camera's QR reader is called 20-odd Python calls deep.
  `micropython-rp2-libc-flash.patch` runs libc and libm from flash rather than RAM, giving the GC heap
  14 KB: nothing that runs while flash is written calls them, and the timings stay within 10%.
- Drawing: rounded rectangles, ellipses and text are drawn in C (a text op places its glyphs once, when
  recorded), and showing the canvas again sends only the box drawn on since. The main menu went from 237 to
  93 ms, moving its selection from 326 to 80 ms.
- Pico-only choices live in `pico/lib/pico_boot.py`, which main.py imports first, not in SeedSigner's
  source: the preload thread only opens the seed storage, DecodeQR takes the camera's bytes, and ScanScreen
  draws its preview and progress between reads rather than in core1's thread. The preview is the camera's
  last frame, drawn by `_gfx` from the camera's memory in greys.

## A regtest spend

`pico/tests/regtest.py` checks the signatures against Bitcoin Core: a watch-only wallet for the test seed
funds P2WPKH beside P2TR, P2PKH, and a 2-of-3 P2SH-P2WSH whose cosigner is another Core wallet. The Pico, set to
Regtest and driven as `psbt_flow.py` drives it, signs each, and the animated QR read back from its screen is
combined with the unsigned PSBT (the signed one holds only its signatures), finalized and mined. The QR took 13
to 23 frames, 42 to 74 s of screenshots. The first spend, a lone P2WPKH shown to the camera, confirmed as txid
d640897e4ff1fa4f75853dd2c89e4f6bcfebd1706fe8411d5386965c4e2f4988.

## What the Pico build gives up

Whatever `signer.wasm` does not do: addresses and message signing off the standard paths (a custom
derivation's xpub is exported), Hindi, Thai, Persian and Arabic, and more than one CJK language at once (upstream's BIP39 wordlist setting is hidden, so
English words only on both). The tests that expect those stay on CPython.

Electrum segwit seeds are read by the signer (`signer_seed_from_electrum`), which also checks their version and
derives their P2WPKH account at m/0h; as upstream, they have no other single sig script type. Upstream's
multisig xpub for them (m/1h) and message signing are refused.

## Needed from bitwasm-signer

- **Messages longer than 1024 bytes.** SeedSigner has no limit; its longest test message is 576.

## Decisions

- **No `seed_bytes`.** The seed is derived inside `signer.wasm` and never leaves it. The active seed's
  key stays loaded while the seed is in `SeedStorage`; choosing another seed re-runs PBKDF2.
  `Seed.seed_bytes` remains only as a CPython-side property for the embit callers not yet moved, and
  goes away at the end of stage 1.
- **The OP_RETURN check is strict**, as upstream's: the signer's option, set at `signer_init`, so other
  hosts may allow what upstream refuses.
- **SegWit v0 inputs are signed without `non_witness_utxo`**, as upstream signs them: also a `signer_init`
  option, off by default, since their amounts are then the PSBT's word. One that is given is still checked.
- **The wordlist is read from `signer.wasm`'s memory**, not copied into Python, which would cost tens
  of KB of heap on the device.
- **Dice rolls keep SeedSigner's method** (SHA-256 of the roll string), which is also what
  `signer_mnemonic_from_dice` does.
