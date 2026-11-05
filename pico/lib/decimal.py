# The part of decimal BtcAmount uses: Decimal from a float or a string, quantize (half-even, the default
# context's rounding), str, and "," formatting. A coefficient and a base-10 exponent
class Decimal:
    def __init__(self, value="0"):
        if isinstance(value, Decimal):
            self.sign, self.coef, self.exp = value.sign, value.coef, value.exp
            return
        s = repr(value) if isinstance(value, float) else str(value)
        s = s.strip().lower()
        self.sign = 1 if s.startswith("-") else 0
        s = s.lstrip("+-")
        exp = 0
        if "e" in s:
            s, e = s.split("e")
            exp = int(e)
        if "." in s:
            whole, frac = s.split(".")
            s, exp = whole + frac, exp - len(frac)
        if not s or not s.isdigit():
            raise ValueError("invalid literal for Decimal: %r" % value)  # decimal raises InvalidOperation
        self.coef, self.exp = int(s), exp

    def quantize(self, other):
        out = Decimal(self)
        shift = other.exp - self.exp
        if shift > 0:
            q, r = divmod(self.coef, 10 ** shift)
            if r * 2 > 10 ** shift or (r * 2 == 10 ** shift and q % 2):
                q += 1
            out.coef = q
        elif shift < 0:
            out.coef = self.coef * 10 ** -shift
        out.exp = other.exp
        return out

    def __str__(self):
        """decimal's to-scientific-string: plain unless the exponent is positive or the number is tiny."""
        digits = str(self.coef)
        adjusted = self.exp + len(digits) - 1
        sign = "-" if self.sign else ""
        if self.exp <= 0 and adjusted >= -6:
            if self.exp == 0:
                return sign + digits
            digits = digits.rjust(-self.exp + 1, "0")
            return sign + digits[:self.exp] + "." + digits[self.exp:]
        mant = digits[0] + ("." + digits[1:] if len(digits) > 1 else "")
        return sign + mant + "E" + ("+" if adjusted >= 0 else "-") + str(abs(adjusted))

    def __format__(self, spec):
        s = str(self)
        if "," not in spec or "E" in s:
            return s
        sign = "-" if s.startswith("-") else ""
        s = s.lstrip("-")
        whole, _, frac = s.partition(".")
        groups = []
        while len(whole) > 3:
            groups.insert(0, whole[-3:])
            whole = whole[:-3]
        groups.insert(0, whole)
        return sign + ",".join(groups) + ("." + frac if frac else "")
