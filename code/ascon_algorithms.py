"""
Ascon algorithms (NIST SP 800-232 / ACVP profile).

Supported algorithms:
- Ascon-AEAD128
- Ascon-Hash256
- Ascon-XOF128
- Ascon-CXOF128
"""

from __future__ import annotations

from typing import Iterable, Literal, TypeAlias

BytesLike: TypeAlias = bytes | bytearray | memoryview
AsconAeadVariant: TypeAlias = Literal["Ascon-AEAD128"]
AsconHashVariant: TypeAlias = Literal["Ascon-Hash256", "Ascon-XOF128", "Ascon-CXOF128"]


def ascon_aead128_encrypt(key: BytesLike, nonce: BytesLike, associated_data: BytesLike, plaintext: BytesLike) -> tuple[bytes, bytes]:
    """Encrypt plaintext and return (ciphertext, tag)."""
    full = ascon_encrypt(key, nonce, associated_data, plaintext, "Ascon-AEAD128")
    return full[:-16], full[-16:]


def ascon_aead128_decrypt(
    key: BytesLike, nonce: BytesLike, associated_data: BytesLike, ciphertext: BytesLike, tag: BytesLike
) -> bytes | None:
    """Decrypt and verify; return plaintext or None on authentication failure."""
    return ascon_decrypt(key, nonce, associated_data, bytes(ciphertext) + bytes(tag), "Ascon-AEAD128")


def ascon_aead128_decrypt_with_taglen(
    key: BytesLike, nonce: BytesLike, associated_data: BytesLike, ciphertext: BytesLike, tag: BytesLike, tag_bits: int
) -> bytes | None:
    """Decrypt and verify using a possibly truncated tag length (ACVP-style)."""
    if tag_bits % 8 != 0:
        raise ValueError("Only byte-aligned tag lengths are supported.")
    tag_bytes = tag_bits // 8
    if len(tag) != tag_bytes:
        raise ValueError(f"Tag length mismatch: got {len(tag)} bytes, expected {tag_bytes}.")

    state = [0, 0, 0, 0, 0]
    k = len(key) * 8
    rounds_a = 12
    rounds_b = 8
    rate = 16

    ascon_initialize(state, k, rate, rounds_a, rounds_b, 1, key, nonce)
    ascon_process_associated_data(state, rounds_b, rate, associated_data)
    plaintext = ascon_process_ciphertext(state, rounds_b, rate, ciphertext)
    full_tag = ascon_finalize(state, rate, rounds_a, key)
    if full_tag[:tag_bytes] == bytes(tag):
        return plaintext
    return None


def ascon_hash256(message: BytesLike) -> bytes:
    return ascon_hash(message, variant="Ascon-Hash256", hashlength=32)


def ascon_xof128(message: BytesLike, out_len: int) -> bytes:
    return ascon_hash(message, variant="Ascon-XOF128", hashlength=out_len)


def ascon_cxof128(message: BytesLike, customization: BytesLike, out_len: int) -> bytes:
    return ascon_hash(message, variant="Ascon-CXOF128", hashlength=out_len, customization=customization)


def ascon_hash(
    message: BytesLike,
    variant: AsconHashVariant = "Ascon-Hash256",
    hashlength: int = 32,
    customization: BytesLike = b"",
) -> bytes:
    versions = {"Ascon-Hash256": 2, "Ascon-XOF128": 3, "Ascon-CXOF128": 4}
    if variant not in versions:
        raise ValueError(f"Unsupported hash variant: {variant}")
    if variant == "Ascon-Hash256" and hashlength != 32:
        raise ValueError("Ascon-Hash256 output length must be 32 bytes.")
    if variant == "Ascon-CXOF128":
        if len(customization) > 256:
            raise ValueError("Customization must be at most 256 bytes for Ascon-CXOF128.")
    elif len(customization) != 0:
        raise ValueError("Customization is only valid for Ascon-CXOF128.")

    rounds_a = 12
    rate = 8
    taglen = 256 if variant == "Ascon-Hash256" else 0

    iv = to_bytes([versions[variant], 0, (rounds_a << 4) + rounds_a]) + int_to_bytes(taglen, 2) + to_bytes([rate, 0, 0])
    state = bytes_to_state(iv + zero_bytes(32))
    ascon_permutation(state, 12)

    if variant == "Ascon-CXOF128":
        z_padding = to_bytes([0x01]) + zero_bytes(rate - (len(customization) % rate) - 1)
        z_length = int_to_bytes(len(customization) * 8, 8)
        z_padded = z_length + to_bytes(customization) + z_padding
        for block in range(0, len(z_padded), rate):
            state[0] ^= bytes_to_int(z_padded[block : block + rate])
            ascon_permutation(state, 12)

    m_padding = to_bytes([0x01]) + zero_bytes(rate - (len(message) % rate) - 1)
    m_padded = to_bytes(message) + m_padding
    for block in range(0, len(m_padded), rate):
        state[0] ^= bytes_to_int(m_padded[block : block + rate])
        ascon_permutation(state, 12)

    out = b""
    while len(out) < hashlength:
        out += int_to_bytes(state[0], rate)
        ascon_permutation(state, 12)
    return out[:hashlength]


def ascon_encrypt(
    key: BytesLike, nonce: BytesLike, associateddata: BytesLike, plaintext: BytesLike, variant: AsconAeadVariant = "Ascon-AEAD128"
) -> bytes:
    versions = {"Ascon-AEAD128": 1}
    if variant not in versions:
        raise ValueError(f"Unsupported AEAD variant: {variant}")
    if len(key) != 16 or len(nonce) != 16:
        raise ValueError("Ascon-AEAD128 requires 16-byte key and 16-byte nonce.")

    state = [0, 0, 0, 0, 0]
    k = len(key) * 8
    rounds_a = 12
    rounds_b = 8
    rate = 16

    ascon_initialize(state, k, rate, rounds_a, rounds_b, versions[variant], key, nonce)
    ascon_process_associated_data(state, rounds_b, rate, associateddata)
    ciphertext = ascon_process_plaintext(state, rounds_b, rate, plaintext)
    tag = ascon_finalize(state, rate, rounds_a, key)
    return ciphertext + tag


def ascon_decrypt(
    key: BytesLike, nonce: BytesLike, associateddata: BytesLike, ciphertext: BytesLike, variant: AsconAeadVariant = "Ascon-AEAD128"
) -> bytes | None:
    versions = {"Ascon-AEAD128": 1}
    if variant not in versions:
        raise ValueError(f"Unsupported AEAD variant: {variant}")
    if len(key) != 16 or len(nonce) != 16 or len(ciphertext) < 16:
        raise ValueError("Ascon-AEAD128 decryption requires 16-byte key/nonce and ciphertext with tag.")

    state = [0, 0, 0, 0, 0]
    k = len(key) * 8
    rounds_a = 12
    rounds_b = 8
    rate = 16

    ascon_initialize(state, k, rate, rounds_a, rounds_b, versions[variant], key, nonce)
    ascon_process_associated_data(state, rounds_b, rate, associateddata)
    plaintext = ascon_process_ciphertext(state, rounds_b, rate, ciphertext[:-16])
    tag = ascon_finalize(state, rate, rounds_a, key)
    if tag == ciphertext[-16:]:
        return plaintext
    return None


def ascon_initialize(state: list[int], k: int, rate: int, rounds_a: int, rounds_b: int, version: int, key: BytesLike, nonce: BytesLike):
    taglen = 128
    iv = to_bytes([version, 0, (rounds_b << 4) + rounds_a]) + int_to_bytes(taglen, 2) + to_bytes([rate, 0, 0])
    state[0], state[1], state[2], state[3], state[4] = bytes_to_state(iv + to_bytes(key) + to_bytes(nonce))
    ascon_permutation(state, rounds_a)

    zero_key = bytes_to_state(zero_bytes(40 - len(key)) + to_bytes(key))
    for i in range(5):
        state[i] ^= zero_key[i]


def ascon_process_associated_data(state: list[int], rounds_b: int, rate: int, associateddata: BytesLike):
    if len(associateddata) > 0:
        a_padding = to_bytes([0x01]) + zero_bytes(rate - (len(associateddata) % rate) - 1)
        a_padded = to_bytes(associateddata) + a_padding
        for block in range(0, len(a_padded), rate):
            state[0] ^= bytes_to_int(a_padded[block : block + 8])
            if rate == 16:
                state[1] ^= bytes_to_int(a_padded[block + 8 : block + 16])
            ascon_permutation(state, rounds_b)
    state[4] ^= 1 << 63


def ascon_process_plaintext(state: list[int], rounds_b: int, rate: int, plaintext: BytesLike) -> bytes:
    p_lastlen = len(plaintext) % rate
    p_padding = to_bytes([0x01]) + zero_bytes(rate - p_lastlen - 1)
    p_padded = to_bytes(plaintext) + p_padding

    ciphertext = b""
    for block in range(0, len(p_padded) - rate, rate):
        state[0] ^= bytes_to_int(p_padded[block : block + 8])
        state[1] ^= bytes_to_int(p_padded[block + 8 : block + 16])
        ciphertext += int_to_bytes(state[0], 8) + int_to_bytes(state[1], 8)
        ascon_permutation(state, rounds_b)

    block = len(p_padded) - rate
    state[0] ^= bytes_to_int(p_padded[block : block + 8])
    state[1] ^= bytes_to_int(p_padded[block + 8 : block + 16])
    ciphertext += int_to_bytes(state[0], 8)[: min(8, p_lastlen)] + int_to_bytes(state[1], 8)[: max(0, p_lastlen - 8)]
    return ciphertext


def ascon_process_ciphertext(state: list[int], rounds_b: int, rate: int, ciphertext: BytesLike) -> bytes:
    c_lastlen = len(ciphertext) % rate
    c_padded = to_bytes(ciphertext) + zero_bytes(rate - c_lastlen)

    plaintext = b""
    for block in range(0, len(c_padded) - rate, rate):
        c0 = bytes_to_int(c_padded[block : block + 8])
        c1 = bytes_to_int(c_padded[block + 8 : block + 16])
        plaintext += int_to_bytes(state[0] ^ c0, 8) + int_to_bytes(state[1] ^ c1, 8)
        state[0], state[1] = c0, c1
        ascon_permutation(state, rounds_b)

    block = len(c_padded) - rate
    c_padx = zero_bytes(c_lastlen) + to_bytes([0x01]) + zero_bytes(rate - c_lastlen - 1)
    c_mask = zero_bytes(c_lastlen) + ff_bytes(rate - c_lastlen)
    c0 = bytes_to_int(c_padded[block : block + 8])
    c1 = bytes_to_int(c_padded[block + 8 : block + 16])
    plaintext += (int_to_bytes(state[0] ^ c0, 8) + int_to_bytes(state[1] ^ c1, 8))[:c_lastlen]
    state[0] = (state[0] & bytes_to_int(c_mask[0:8])) ^ c0 ^ bytes_to_int(c_padx[0:8])
    state[1] = (state[1] & bytes_to_int(c_mask[8:16])) ^ c1 ^ bytes_to_int(c_padx[8:16])
    return plaintext


def ascon_finalize(state: list[int], rate: int, rounds_a: int, key: BytesLike) -> bytes:
    key = to_bytes(key)
    state[rate // 8 + 0] ^= bytes_to_int(key[0:8])
    state[rate // 8 + 1] ^= bytes_to_int(key[8:16])
    ascon_permutation(state, rounds_a)
    state[3] ^= bytes_to_int(key[-16:-8])
    state[4] ^= bytes_to_int(key[-8:])
    return int_to_bytes(state[3], 8) + int_to_bytes(state[4], 8)


def ascon_permutation(state: list[int], rounds: int = 1):
    if rounds > 12:
        raise ValueError("Ascon permutation rounds must be <= 12.")
    for r in range(12 - rounds, 12):
        state[2] ^= 0xF0 - (r * 0x10) + r

        state[0] ^= state[4]
        state[4] ^= state[3]
        state[2] ^= state[1]
        t = [(state[i] ^ 0xFFFFFFFFFFFFFFFF) & state[(i + 1) % 5] for i in range(5)]
        for i in range(5):
            state[i] ^= t[(i + 1) % 5]
        state[1] ^= state[0]
        state[0] ^= state[4]
        state[3] ^= state[2]
        state[2] ^= 0xFFFFFFFFFFFFFFFF

        state[0] ^= rotr(state[0], 19) ^ rotr(state[0], 28)
        state[1] ^= rotr(state[1], 61) ^ rotr(state[1], 39)
        state[2] ^= rotr(state[2], 1) ^ rotr(state[2], 6)
        state[3] ^= rotr(state[3], 10) ^ rotr(state[3], 17)
        state[4] ^= rotr(state[4], 7) ^ rotr(state[4], 41)


def zero_bytes(n: int) -> bytes:
    return b"\x00" * n


def ff_bytes(n: int) -> bytes:
    return b"\xFF" * n


def to_bytes(values: BytesLike | Iterable[int]) -> bytes:
    return bytes(values)


def bytes_to_int(buf: BytesLike) -> int:
    return int.from_bytes(bytes(buf), "little")


def int_to_bytes(value: int, nbytes: int) -> bytes:
    return int(value).to_bytes(nbytes, "little")


def bytes_to_state(buf: bytes) -> list[int]:
    return [bytes_to_int(buf[8 * w : 8 * (w + 1)]) for w in range(5)]


def rotr(value: int, r: int) -> int:
    return ((value >> r) | ((value & ((1 << r) - 1)) << (64 - r))) & 0xFFFFFFFFFFFFFFFF
