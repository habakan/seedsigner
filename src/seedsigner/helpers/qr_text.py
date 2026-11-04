"""
decode_qr's regular expressions as string code: MicroPython's re has neither flags nor {m,n}.
Each function answers exactly what the expression in its docstring does, case-insensitively where that
expression was; tests/test_qr_text.py checks them against re on generated strings.
"""
_DIGITS = "0123456789"
_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ALNUM = set(_DIGITS + _UPPER + _UPPER.lower())
_B64 = _ALNUM | set("+/=")


def _run(s: str, i: int, chars) -> int:
    """How many characters from s[i] on are in `chars`."""
    j = i
    while j < len(s) and s[j] in chars:
        j += 1
    return j - i


def part_header(s: str):
    """r'^p(\\d+)of(\\d+) ', re.I: (part, of, the rest) or None."""
    if not s or s[0] not in "pP":
        return None
    n = _run(s, 1, _DIGITS)
    i = 1 + n
    if not n or s[i:i + 2].lower() != "of":
        return None
    m = _run(s, i + 2, _DIGITS)
    j = i + 2 + m
    if not m or s[j:j + 1] != " ":
        return None
    return int(s[1:i]), int(s[i + 2:j]), s[j + 1:]


def is_specter_psbt_part(s: str) -> bool:
    """r'^p(\\d+)of(\\d+) ([A-Za-z0-9+\\/=]+$)', re.I"""
    h = part_header(s)
    if h is None:
        return False
    rest = h[2][:-1] if h[2].endswith("\n") else h[2]  # $ also matches before a final newline
    return len(rest) > 0 and all(c in _B64 for c in rest)


def is_bbqr(s: str) -> bool:
    """r'^B\\$[2HZ]P[0-9A-Z]{4}' (case-sensitive)"""
    return len(s) >= 8 and s[:2] == "B$" and s[2] in "2HZ" and s[3] == "P" and all(c in _DIGITS + _UPPER for c in s[4:8])


def has_digit_run(s: str, n: int = 48) -> bool:
    """r'\\d{48,96}' searched anywhere: a run of at least 48 digits."""
    i = 0
    while i < len(s):
        r = _run(s, i, _DIGITS)
        if r >= n:
            return True
        i += r + 1
    return False


def is_specter_wallet_json(s: str) -> bool:
    """r'^\\{\\"label\\".*\\"descriptor\\"\\:.*', re.I, on a string without newlines."""
    low = s.lower()
    return low.startswith('{"label"') and '"descriptor":' in low[8:]


def is_address(s: str) -> bool:
    """r'^bitcoin\\:.*' or r'^((bc1|tb1|bcr|[123]|[mn])[a-zA-HJ-NP-Z0-9]{25,62})$', both re.I"""
    low = s.lower()
    if low.startswith("bitcoin:"):
        return True
    for body in (low, low[:-1] if low.endswith("\n") else None):
        if body is None:
            continue
        for prefix in ("bc1", "tb1", "bcr", "1", "2", "3", "m", "n"):
            rest = body[len(prefix):]
            if body.startswith(prefix) and 25 <= len(rest) <= 62 and all(c in _ALNUM for c in rest):
                return True
    return False


def match_address(s: str):
    """r'^((bc1q|tb1q|bcrt1q|bc1p|tb1p|bcrt1p|[123]|[mn])[a-zA-HJ-NP-Z0-9]{25,64})', re.I:
    (group 1, the address; group 2, its prefix) or None."""
    low = s.lower()
    for prefix in ("bc1q", "tb1q", "bcrt1q", "bc1p", "tb1p", "bcrt1p", "1", "2", "3", "m", "n"):
        if low.startswith(prefix):
            r = min(_run(s, len(prefix), _ALNUM), 64)
            if r >= 25:
                return s[:len(prefix) + r], s[:len(prefix)]
    return None


def two_numbers(s: str):
    """r'(\\d+)\\D*(\\d+)' searched: the first two numbers, (m, n), or None."""
    i = 0
    while i < len(s):
        if s[i] not in _DIGITS:
            i += 1
            continue
        r1 = _run(s, i, _DIGITS)
        j = i + r1
        while j < len(s) and s[j] not in _DIGITS:
            j += 1
        r2 = _run(s, j, _DIGITS)
        if r2:
            return int(s[i:i + r1]), int(s[j:j + r2])
        if r1 >= 2:  # the backtrack: the run's last digit is the second number
            return int(s[i:i + r1 - 1]), int(s[i + r1 - 1])
        i += r1
    return None


def four_letter_word(wordlist, x: str):
    """The word whose first four letters are x, as [w[:4] for w in wordlist].index(x) finds it, or None.
    A binary search: building that list each time is 2048 strings, more than the Pico's heap spares."""
    lo, hi = 0, len(wordlist)
    while lo < hi:
        mid = (lo + hi) // 2
        if wordlist[mid] < x:
            lo = mid + 1
        else:
            hi = mid
    return wordlist[lo] if lo < len(wordlist) and wordlist[lo][:4] == x else None
