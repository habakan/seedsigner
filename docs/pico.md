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
- MicroPython has no `sha512`, `pbkdf2_hmac` or secp256k1, so embit cannot come along anyway.

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
make -C pico rp2 BITWASM_SIGNER=<bitwasm-signer> PICO_TOOLCHAIN_PATH=<RISC-V GCC>   # then flash firmware.elf
make -C pico device-install PORT=/dev/cu.usbmodem...    # main.py, once
make -C pico mpy && make -C pico device-smoke PORT=...  # or run a script with the modules mounted
```

## PSBTs without embit

`models/psbt_wasm.py`'s `WasmPSBTParser` gives the PSBT views what embit's `PSBTParser` does, from
`parser.wasm`'s plan and the signer's review alone; `models/psbt.py` picks it where embit is missing.
`tests/conftest.py` repeats every successful embit parse in the suite with it and compares what the views
read: 118 parses agree. `tests/test_flows_psbt_wasm.py` scans, reviews and signs through the views with
both parsers, and `pico/tests/psbt.py` prints the same review and signed PSBT on the Pico 2 as on CPython.

Two differences, both from the signer checking each output itself:

- P2WSH change without a registered multisig descriptor is an external spend, where embit presumes it
  change from the psbt's claims (37 of the 118 parses, where the change fields are not compared).
- Inputs of mixed script types are accepted; embit's parser refuses them as "Mixed inputs".

The signed PSBT is what `parser_finalize` writes, untrimmed: the Pico has no embit to trim it with.

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

## What the Pico build gives up

Whatever `signer.wasm` does not do: Electrum seeds, non-English wordlists, legacy P2PKH, custom
derivation paths, and multisig beyond three keys. The tests that expect those stay on CPython.

## Needed from bitwasm-signer

- **An address at a given index.** `signer_find_address` searches; the address explorer lists.
- **Messages longer than 512 bytes.** SeedSigner has no limit, and one of its test messages is 576.

## Decisions

- **No `seed_bytes`.** The seed is derived inside `signer.wasm` and never leaves it. The active seed's
  key stays loaded while the seed is in `SeedStorage`; choosing another seed re-runs PBKDF2.
  `Seed.seed_bytes` remains only as a CPython-side property for the embit callers not yet moved, and
  goes away at the end of stage 1.
- **The wordlist is read from `signer.wasm`'s memory**, not copied into Python, which would cost tens
  of KB of heap on the device.
- **Dice rolls keep SeedSigner's method** (SHA-256 of the roll string), which is also what
  `signer_mnemonic_from_dice` does.
