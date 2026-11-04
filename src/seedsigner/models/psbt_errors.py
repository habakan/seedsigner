"""The ways a psbt is refused, shared by the embit parser and the wasm one; needs no embit."""



class PSBTVerificationError(Exception):
    """
    Base for the checks that reject a psbt outright while it is being parsed.

    A psbt that trips one of these is never shown to the user. The view layer should catch
    these exceptions and route to a warning (the severity of which and the allowed next
    steps are determined by the specific subclass error encountered).
    """
    pass


class PSBTOutputOwnershipClaimError(PSBTVerificationError):
    """
    An output claims this seed's fingerprint on a key the seed does not derive.

    This is asserting that an output belongs to this seed when it does not. We treat this
    deception as an attack.
    """
    pass


class PSBTInputOwnershipClaimError(PSBTVerificationError):
    """
    An input claims this seed's fingerprint on a key the seed does not derive.

    The same type of false claim as the output case above, but a forged input claim simply
    renders the psbt unsignable (embit re-derives the real key and will refuse to sign on
    a mismatch) so there's no point in continuing.
    """
    pass


class PSBTSurplusDerivationPathsError(PSBTVerificationError):
    """
    Raised for three similar cases:
      * single sig: output has more than one derivation path entry.
      * multisig: an output confirmed to pay this seed claims more derivation path
        entries than its committed script has keys.
      * taproot: output has more than one derivation path entry claiming to be its
        internal key (i.e. claiming no leaf hashes).

    For single sig this is clearly a structural error and is not expected to be seen in
    the real world but it's worth the sanity check.

    For multisig, this could be an attempt to deceive the user, but we do not try to
    adjudicate that.
    """
    pass


class PSBTMixedDerivationPathTypesError(PSBTVerificationError):
    """
    An input or output declares derivation paths in both the ecdsa and the taproot key
    maps (bip32_derivations and taproot_bip32_derivations).

    This is a correctness problem (not expected to be seen in the real world) or
    potentially a weak form of deception, but we do not try to adjudicate that.
    """
    pass


class PSBTOutputOwnershipContradictionError(PSBTVerificationError):
    """
    The psbt's account of who an output pays contradicts which key(s) the output
    actually commits to.

    For multisig, it's one of:
      * The output claims one of our keys, but the script the psbt supplied for it does
        not match what the output actually commits to (the output's scriptPubKey).
      * The output claims that one of our keys is part of the multisig that owns the
        output, but that key is not part of the scriptPubKey commitment.
      * Our seed owns a key that is part of the scriptPubKey commitment, but the output
        claims a different seed in our place, by fingerprint or by listed public key.

    Single sig supplies no script, so both contradictions come from the rebuild alone: the
    output claims our key but commits to another key, or it commits to our key while
    claiming a different fingerprint in our place.

    We treat any of these deceptions as an attack.
    """
    pass


class PSBTInputAmountVerificationError(PSBTVerificationError):
    """
    An input's declared amount is unproven or false, so the fee displayed cannot be trusted.
    It's one of these:
      * The input has no non_witness_utxo and its sighash doesn't commit to its amount.
      * The input's non_witness_utxo doesn't hash to the txid the input references.
      * The input's witness_utxo contradicts the verified non_witness_utxo.

    We treat any of these as an attack.
    """
    pass


class PSBTBitwasmRefusedError(PSBTVerificationError):
    """
    signer.wasm (bitwasm-signer) would not sign this psbt: a script, sighash or size it does
    not support, or a check of its own that failed. Only signer.wasm signs, so the psbt
    stops here.
    """
    pass


class PSBTMissingInputUtxoError(PSBTVerificationError):
    """
    An input is missing its utxo, which holds its amount. A psbt supplies the amount in
    the witness_utxo or non_witness_utxo field, and without either there is no amount to
    verify. This is a correctness problem rather than an attack.
    """
    pass


class PSBTMalformedOpReturnError(PSBTVerificationError):
    """
    An OP_RETURN output's script is not made of complete pushes: a push runs past the end
    of the script, or an opcode is not a push at all.

    This is a malformed psbt rather than a proven deception, so we do not treat it as an
    attack.
    """
    pass


class PSBTMissingInputScriptError(PSBTVerificationError):
    """
    An input is missing a required script.

    Required scripts:
      * p2wsh: witness_script
      * p2sh: redeem_script
      * p2sh-p2wsh (nested segwit multisig): witness_script and redeem_script

    This is a correctness problem rather than an attack.
    """
    pass


class PSBTInputScriptMismatchError(PSBTVerificationError):
    """
    An input supplied a script that doesn't match what the input actually commits to.

    This sort of misleading script can lead the parser to an incorrect determination of
    whether an output is our change.

    We treat this deception as an attack.
    """
    pass


class PSBTExtraneousInputScriptError(PSBTVerificationError):
    """
    An input commits to a specific script type but also supplies an extraneous script that
    is not used by that script type (e.g. a redeem script is meaningless for native
    segwit).

    We don't try to decide whether this is an attack or a mistake.
    """
    pass


class PSBTBitwasmDisagreementError(PSBTVerificationError):
    """
    embit's reading of the psbt and signer.wasm's review of the same bytes disagree on the
    fee, on which outputs come back to this seed, or on where the rest goes. The screens
    come from one and the signature from the other, so we refuse rather than pick one.
    """
    pass


class PSBTSeedCannotSignError(PSBTVerificationError):
    """
    The selected seed holds no key that could sign any input.

    This is a mismatch rather than an attack: the usual cause is the user picking the
    wrong seed. It is raised so the flow can say so up front, instead of walking the user
    through reviewing and approving a transaction that would then produce no signatures.
    """
    pass
