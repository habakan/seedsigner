import random
import re

import pytest

from seedsigner.helpers import qr_text

# Pieces that steer generated strings into each expression's interesting cases
PIECES = ["p", "P", "of", "OF", " ", "1", "23", "0", "9" * 30, "B$", "Z", "H", "2", "PA1B", "bc1q", "BC1P",
          "tb1", "bcrt1q", "bcr", "m", "n", "bitcoin:", "BITCOIN:", "+", "/", "=", "a" * 30, "XYZ", "iI", "oO",
          "\n", ":", '{"label"', '"descriptor":', "-", "q" * 20, "of 3", "é"]


def shaped(rnd):
    """Close to a part header or a BBQr one, sometimes off by a piece."""
    digits = lambda: "".join(rnd.choice("0123456789x") for _ in range(rnd.randint(0, 3)))
    tail = "".join(rnd.choice(PIECES + ["QUJD", "aGVsbG8="]) for _ in range(rnd.randint(0, 3)))
    if rnd.random() < 0.5:
        return rnd.choice("pPq") + digits() + rnd.choice(["of", "OF", "Of", "o", ""]) + digits() + rnd.choice([" ", "", "  "]) + tail
    return rnd.choice(["B$", "B", "b$"]) + rnd.choice("2HZXp") + rnd.choice("PQp") + \
        "".join(rnd.choice("0A9Zaz-") for _ in range(rnd.randint(2, 5))) + tail


def strings(seed, count=20000):
    rnd = random.Random(seed)
    for _ in range(count):
        if rnd.random() < 0.5:
            yield shaped(rnd)
        else:
            yield "".join(rnd.choice(PIECES) for _ in range(rnd.randint(0, 8)))


CASES = [
    (qr_text.is_specter_psbt_part, lambda s: bool(re.search(r'^p(\d+)of(\d+) ([A-Za-z0-9+\/=]+$)', s, re.IGNORECASE))),
    (qr_text.is_bbqr, lambda s: bool(re.search(r"^B\$[2HZ]P[0-9A-Z]{4}", s))),
    (qr_text.has_digit_run, lambda s: bool(re.search(r'\d{48,96}', s))),
    (qr_text.is_specter_wallet_json, lambda s: bool(re.search(r'^\{\"label\".*\"descriptor\"\:.*', s.replace("\n", ""), re.IGNORECASE))),
    (qr_text.is_address, lambda s: bool(re.search(r'^bitcoin\:.*', s, re.IGNORECASE) or
                                        re.search(r'^((bc1|tb1|bcr|[123]|[mn])[a-zA-HJ-NP-Z0-9]{25,62})$', s, re.IGNORECASE))),
]


@pytest.mark.parametrize("ours,regex", CASES, ids=[c[0].__name__ for c in CASES])
def test_matches_the_regular_expression(ours, regex):
    for s in strings(ours.__name__):
        if ours is qr_text.is_specter_wallet_json:
            s = s.replace("\n", "")
        assert ours(s) == regex(s), repr(s)


def test_part_header_and_groups():
    for s in strings("part_header"):
        m = re.search(r'^p(\d+)of(\d+) (.*)', s, re.IGNORECASE | re.DOTALL)
        assert qr_text.part_header(s) == ((int(m.group(1)), int(m.group(2)), m.group(3)) if m else None), repr(s)


def test_match_address():
    pattern = r'^((bc1q|tb1q|bcrt1q|bc1p|tb1p|bcrt1p|[123]|[mn])[a-zA-HJ-NP-Z0-9]{25,64})'
    for s in strings("match_address"):
        m = re.search(pattern, s, re.IGNORECASE)
        assert qr_text.match_address(s) == ((m.group(1), m.group(2)) if m else None), repr(s)


def test_two_numbers():
    for s in strings("two_numbers"):
        m = re.search(r'(\d+)\D*(\d+)', s)
        assert qr_text.two_numbers(s) == ((int(m.group(1)), int(m.group(2))) if m else None), repr(s)


def test_four_letter_word():
    from seedsigner.models.seed import Seed
    wordlist = Seed.get_wordlist()
    four = [w[:4].strip() for w in wordlist]
    tries = {w[:n] for w in wordlist for n in range(1, 6)} | set(strings("four_letter_word", 5000))
    for x in tries:
        assert qr_text.four_letter_word(wordlist, x) == (wordlist[four.index(x)] if x in four else None), repr(x)


def test_ur_crc32_is_the_table_it_replaced():
    from seedsigner.helpers.ur2.crc32 import crc32
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) if c % 2 == 0 else 0xEDB88320 ^ (c >> 1)
        table.append(c)

    def by_table(buf):
        crc = 0xFFFFFFFF
        for b in buf:
            crc = (crc >> 8) ^ table[(crc ^ b) & 0xFF]
        return 0xFFFFFFFF & ~crc

    rnd = random.Random("crc32")
    for n in [0, 1, 4, 255, 5666] + [rnd.randint(0, 600) for _ in range(300)]:
        buf = bytes(rnd.getrandbits(8) for _ in range(n))
        assert crc32(buf) == by_table(buf)
