# Only ASCII, which every form leaves as it is: the Pico build takes ASCII mnemonics and passphrases,
# as bitwasm-signer-pico does, rather than carry the Unicode tables
def normalize(form, s):
    for c in s:
        if ord(c) > 127:
            raise ValueError("only ASCII text on this device")
    return s
