# SeedSigner on the Raspberry Pi Pico 2

SeedSigner's own Python, its controller, views and models, running on an RP2350 under MicroPython 1.29,
with a 240x240 ST7789 screen, a DVP camera, a joystick and three keys. The flows are upstream's: the
same screens, in the same order, from the same source. What changes is underneath them.

This is a working fork, not a proposal to merge. It is here to show that the RP2350's 520 KB is enough
for SeedSigner with a live camera preview, which [SeedSigner#244](https://github.com/SeedSigner/seedsigner/issues/244)
doubted for the RP2040, and to show one way of getting there.

## What works

On the device, with nothing but the buttons and the camera:

- New seeds from a camera image (upstream's 50 preview frames and a final image) or from dice; 12 or 24
  words entered on the keyboard; SeedQR and CompactSeedQR, read and shown; BIP39 passphrases.
- Xpub export as an animated or static QR, the address explorer, address verification, BIP85 child seeds,
  message signing.
- PSBTs scanned as animated UR, reviewed on upstream's screens (overview, inputs, outputs, change, fee)
  and signed: P2WPKH, P2SH-P2WPKH, P2TR, P2PKH, and P2WSH, P2SH-P2WSH and P2SH multisig, P2WSH change
  verified against a registered descriptor. A 25 KB PSBT of ten inputs and 200 outputs signs.
- The UI in English and 15 more languages (one CJK language per build).

Checked against other software, not only against itself:

- A Sparrow wallet on signet, made from the device's xpub, built a spend that the device signed through
  the camera; Sparrow read the signed QR back and broadcast it
  ([43980b4e…](https://mempool.space/signet/tx/43980b4e4e75da68c2f9181fea3864603cc0d145885d42072cfa7c5d3e403a1a)).
- `pico/tests/regtest.py`: Bitcoin Core funds P2WPKH and P2TR, P2PKH, and 2-of-3 P2SH-P2WSH and P2SH;
  the device signs each, the signed QR is read off its screen, and Core finalizes and mines it.
- `pico/tests/psbt_flow.py`: each signed PSBT is the same bytes upstream SeedSigner produces from the
  same PSBT (P2TR differs by design: the signature stays a `tap_key_sig`).
- `pico/tests/seed_flow.py`: a seed made from the camera is read back from its SeedQR and its xpub QR;
  the words are a valid mnemonic whose xpub, derived on the host, is the one the device shows.
- Without the device: `make -C pico sim` builds the same Python into MicroPython's unix port (Linux), where
  `psbt_flow.py sim` drives the same screens ([docs/pico.md](../docs/pico.md#without-the-device)).

## Measured

RP2350 RISC-V at 150 MHz, MicroPython 1.29.

| | |
|---|---:|
| GC heap / free on the main menu / free through a PSBT review | 249 KB / 85 KB / 53-72 KB |
| static RAM / of it, WAMR's pool, lent to the camera and QR reader while scanning | about 245 KB / 110 KB |
| firmware (SeedSigner and 15 languages frozen in) / flash | 2.3 MB / 4 MB |
| reading one QR frame | 0.33-0.44 s |
| a 21-frame animated UR PSBT, from Scan to the review | 15-33 s |
| seed from mnemonic (PBKDF2) / one address | 0.55 s / 27 ms |
| 50 camera frames for a new seed | 19 s |

There is no framebuffer: screens are drawn 40 rows at a time, and the camera's 320x240 frame lives in
memory the PSBT parser does not need while a code is being scanned.

## How it differs from upstream's MicroPython port

Upstream is porting SeedSigner to MicroPython on the ESP32-P4
([seedsigner-micropython-builder](https://github.com/kdmukai/seedsigner-micropython-builder)). The two
went different ways because the boards are different:

| | upstream (ESP32-P4) | this fork (RP2350) |
|---|---|---|
| memory | PSRAM | 520 KB SRAM, no PSRAM |
| screens | native LVGL screens behind a JSON screen contract | upstream's PIL screens, on a small PIL written for the Pico ([micropython-pil](https://github.com/habakan/micropython-pil), drawing in C) |
| keys and PSBTs | embit, with C modules for secp256k1 and hashing | [bitwasm-signer](https://github.com/bitwasm-project/bitwasm-signer): its C signer linked in, its PSBT parser in WebAssembly on WAMR |
| UR | cUR, in C | upstream's pure-Python ur2, with the heap in mind |
| QR reading | | a Rust reader on the camera frame, in C |

The signer is the larger difference. Stock MicroPython has no SHA-512, PBKDF2 or secp256k1, and the
RP2350 has no room for a second copy of what a PSBT parse holds. bitwasm-signer keeps every key inside
one C module whose review of a PSBT is checked against Bitcoin Core, and parses the PSBT, the one input
an attacker controls, inside a WebAssembly sandbox. embit itself was tried on the RP2350, with C modules for
its crypto: it ran out of heap on a two-input PSBT, where this build signs 25 KB ones (`docs/pico.md`,
"Why not embit").

## What changed in SeedSigner's source

Kept apart so upstream's changes can still be merged in:

1. **embit replaced by bitwasm-signer**: `helpers/bitwasm.py`, `helpers/wallet.py`, `models/psbt_wasm.py`
   and the places that called embit. On CPython the test suite runs both and compares: every PSBT parse
   in upstream's tests is repeated with the wasm parser, and what the views read must agree.
2. **MicroPython portability**: no regex features MicroPython lacks, no f-strings it cannot parse, fewer
   allocations late in a flow. Small, and harmless on the Pi.
3. **Pico-only**, under `pico/`: the PIL, the display, camera, WAMR and signer modules, MicroPython
   patches, build tools, and `pico/lib/pico_boot.py`, which adjusts upstream's classes at boot rather
   than editing them (a heap-bounded UR decoder, the camera preview drawn between reads, no SD card
   notice).

Of upstream's tests, four expect what the signer refuses (two malformed PSBTs, a PSBT this seed has
already signed, an OP_RETURN over 80 bytes); they are marked in `tests/conftest.py` with their reasons.

## Limits

- One core runs SeedSigner's threads; the camera preview is grey.
- No Hindi, Thai, Persian or Arabic (MicroPython has no text shaping), and one CJK language per build.
- Addresses and message signing only on the standard paths; Electrum seeds only as single sig.
- The heap is the risk: some screens have little to spare, and a scan that runs out of it stops
  advancing. The development build logs what the UR decoder drops.

## More

`docs/pico.md` is the engineering record: each stage, what MicroPython needed, how the RAM was found,
the parts and wiring ([Hardware](../docs/pico.md#hardware)), and how to build and flash.
