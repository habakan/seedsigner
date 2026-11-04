#
# crc32.py
#
# Copyright © 2020 Foundation Devices, Inc.
# Licensed under the "BSD-2-Clause Plus Patent License"
#

import binascii

from .constants import MAX_UINT32

def bit_length(n):
    return len(bin(abs(n))) - 2

def crc32(buf):
    # binascii's C CRC-32 (IEEE, as the table this replaced): in Python, every step past 2**30
    # was a heap object on MicroPython, and a frame's worth of them left the heap in pieces
    return MAX_UINT32 & binascii.crc32(buf)

def crc32n(buf):
    n = crc32(buf)
    # The UR spec's Bytewords checksum is a fixed-width 4-byte big-endian CRC32.
    # Sizing the output to the value's bit length emits 3 bytes whenever the CRC is
    # below 2**24 (~1 in 256), which produces frames that spec-compliant decoders
    # reject and that lax decoders truncate by one payload byte.
    return n.to_bytes(4, 'big')
