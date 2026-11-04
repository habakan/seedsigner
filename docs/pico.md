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

## What the Pico build gives up

Whatever `signer.wasm` does not do: Electrum seeds, non-English wordlists, legacy P2PKH, custom
derivation paths, and multisig beyond three keys. The tests that expect those stay on CPython.

## Decisions

- **No `seed_bytes`.** The seed is derived inside `signer.wasm` and never leaves it. The active seed's
  key stays loaded while the seed is in `SeedStorage`; choosing another seed re-runs PBKDF2.
  `Seed.seed_bytes` remains only as a CPython-side property for the embit callers not yet moved, and
  goes away at the end of stage 1.
- **The wordlist is read from `signer.wasm`'s memory**, not copied into Python, which would cost tens
  of KB of heap on the device.
- **Dice rolls keep SeedSigner's method** (SHA-256 of the roll string), which is also what
  `signer_mnemonic_from_dice` does.
